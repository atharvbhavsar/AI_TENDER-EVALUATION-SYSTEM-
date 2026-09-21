"""Domain service for aggregating bidder-level overall eligibility evaluations."""

import logging
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.aggregation.engine import (
    CriterionEvaluationInput,
    aggregate_criteria_results,
)
from app.aggregation.schemas import CriterionBreakdownItem
from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import (
    CriterionEvaluation,
    EvaluationResult,
)
from app.db.models.tender_criterion import (
    ApprovalStatus,
    RequirementType,
    TenderCriterion,
)

logger = logging.getLogger("app.aggregation.service")


def aggregate_submission_evaluation(
    db: Session,
    submission_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    policy_version: str = "v1.0",
    evaluation_run_id: Optional[uuid.UUID] = None,
    run_rules: bool = False,
    auto_generate_reviews: bool = False,
) -> BidderEvaluation:
    """
    Deterministically aggregate all approved criterion evaluations for a bidder submission
    and persist an immutable BidderEvaluation record.

    Enforces:
    - Exact tender_version, bidder, and submission isolation.
    - Only APPROVED criteria participate in authoritative evaluation.
    - Missing mandatory evaluations safely route to MANUAL_REVIEW.
    - Optional criteria failures do NOT independently disqualify the bidder.
    - Zero LLM involvement in decision logic.
    """
    # 1. Fetch and validate BidSubmission
    submission = db.get(BidSubmission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission {submission_id} not found.",
        )

    tender_version = submission.tender_version
    if not tender_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender version for submission {submission_id} not found.",
        )

    tender_id = tender_version.tender_id
    tender_version_id = submission.tender_version_id
    bidder_id = submission.bidder_id
    effective_run_id = evaluation_run_id or uuid.uuid4()

    # 2. Fetch all APPROVED criteria for the exact tender version
    criteria_stmt = (
        select(TenderCriterion)
        .where(
            TenderCriterion.tender_version_id == tender_version_id,
            TenderCriterion.approval_status == ApprovalStatus.APPROVED,
        )
        .order_by(TenderCriterion.criterion_code.asc())
    )
    approved_criteria = list(db.execute(criteria_stmt).scalars().all())

    # Optional: Execute OPA rule evaluation for each approved criterion before aggregation
    if run_rules and approved_criteria:
        from app.rules.service import evaluate_submission_criterion
        for crit in approved_criteria:
            try:
                evaluate_submission_criterion(
                    db=db,
                    submission_id=submission_id,
                    criterion_id=crit.id,
                    user_id=user_id,
                    evaluation_run_id=effective_run_id,
                )
            except Exception as exc:
                logger.warning(
                    "Error executing OPA rule evaluation for criterion %s: %s",
                    crit.criterion_code,
                    str(exc),
                )

    # 3. Fetch all CriterionEvaluation records for this submission
    eval_stmt = (
        select(CriterionEvaluation)
        .where(CriterionEvaluation.bid_submission_id == submission_id)
        .order_by(CriterionEvaluation.evaluated_at.desc())
    )
    all_evaluations = list(db.execute(eval_stmt).scalars().all())

    # Build latest evaluation map keyed by criterion_id
    eval_map = {}
    for eval_item in all_evaluations:
        if eval_item.criterion_id not in eval_map:
            eval_map[eval_item.criterion_id] = eval_item

    # 4. Prepare standardized inputs for aggregation engine
    engine_inputs: List[CriterionEvaluationInput] = []
    for criterion in approved_criteria:
        # Determine if criterion is mandatory
        is_mandatory = (
            criterion.requirement_type == RequirementType.MANDATORY
            or bool(criterion.mandatory) is True
        )

        matched_eval = eval_map.get(criterion.id)
        if matched_eval:
            engine_inputs.append(
                CriterionEvaluationInput(
                    criterion_id=str(criterion.id),
                    criterion_code=criterion.criterion_code,
                    criterion_name=criterion.name,
                    requirement_type=criterion.requirement_type,
                    is_mandatory=is_mandatory,
                    result=matched_eval.result,
                    has_evaluation=True,
                    evaluation_id=str(matched_eval.id),
                    rule_version=matched_eval.rule_version,
                    explanation=matched_eval.explanation or {},
                    evidence_ids=matched_eval.evidence_ids or [],
                )
            )
        else:
            # Mandatory/Optional criterion with no evaluation record
            engine_inputs.append(
                CriterionEvaluationInput(
                    criterion_id=str(criterion.id),
                    criterion_code=criterion.criterion_code,
                    criterion_name=criterion.name,
                    requirement_type=criterion.requirement_type,
                    is_mandatory=is_mandatory,
                    result=EvaluationResult.MANUAL_REVIEW,
                    has_evaluation=False,
                    evaluation_id=None,
                    rule_version=None,
                    explanation={"reason": "Criterion has no deterministic evaluation record."},
                    evidence_ids=[],
                )
            )

    # 5. Run pure deterministic aggregation
    agg_result = aggregate_criteria_results(engine_inputs, policy_version=policy_version)

    # 6. Persist immutable BidderEvaluation record
    bidder_eval = BidderEvaluation(
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        bidder_id=bidder_id,
        bid_submission_id=submission_id,
        evaluation_run_id=effective_run_id,
        result=agg_result.overall_result,
        aggregation_policy_version=policy_version,
        criterion_count=agg_result.criterion_count,
        eligible_count=agg_result.eligible_count,
        not_eligible_count=agg_result.not_eligible_count,
        manual_review_count=agg_result.manual_review_count,
        mandatory_criterion_count=agg_result.mandatory_criterion_count,
        mandatory_eligible_count=agg_result.mandatory_eligible_count,
        mandatory_not_eligible_count=agg_result.mandatory_not_eligible_count,
        mandatory_manual_review_count=agg_result.mandatory_manual_review_count,
        optional_criterion_count=agg_result.optional_criterion_count,
        optional_eligible_count=agg_result.optional_eligible_count,
        optional_not_eligible_count=agg_result.optional_not_eligible_count,
        optional_manual_review_count=agg_result.optional_manual_review_count,
        rule_version_snapshot=agg_result.rule_version_snapshot,
        explanation=agg_result.explanation,
        evaluated_by=user_id,
    )
    db.add(bidder_eval)
    db.commit()
    db.refresh(bidder_eval)

    # Optional: Auto-generate review cases for MANUAL_REVIEW items
    if auto_generate_reviews and (agg_result.overall_result == EvaluationResult.MANUAL_REVIEW or agg_result.manual_review_count > 0):
        try:
            from app.reviews.service import generate_review_cases_for_submission
            generate_review_cases_for_submission(
                db=db,
                submission_id=submission_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning(
                "Error auto-generating review cases for submission %s: %s",
                submission_id,
                str(exc),
            )

    # Record transactional audit event
    try:
        from app.audit.service import AuditService
        AuditService.record(
            db=db,
            action="SUBMISSION_EVALUATION_COMPLETED",
            entity_type="BID_SUBMISSION",
            entity_id=str(submission_id),
            actor_id=user_id,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            bidder_id=bidder_id,
            bid_submission_id=submission_id,
            evaluation_id=bidder_eval.id,
            metadata_json={
                "overall_result": bidder_eval.result.value,
                "evaluation_run_id": str(effective_run_id),
                "criterion_count": bidder_eval.criterion_count,
                "eligible_count": bidder_eval.eligible_count,
                "not_eligible_count": bidder_eval.not_eligible_count,
                "manual_review_count": bidder_eval.manual_review_count,
            },
        )
        db.commit()
    except Exception as exc:
        logger.warning("Audit record warning for submission evaluation %s: %s", submission_id, str(exc))

    logger.info(
        "Persisted overall evaluation for submission %s: result=%s (run_id=%s)",
        submission_id,
        bidder_eval.result,
        bidder_eval.evaluation_run_id,
    )
    return bidder_eval


def get_latest_submission_evaluation(
    db: Session,
    submission_id: uuid.UUID,
) -> BidderEvaluation:
    """Retrieve the most recent overall BidderEvaluation for a submission."""
    submission = db.get(BidSubmission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission {submission_id} not found.",
        )

    stmt = (
        select(BidderEvaluation)
        .where(BidderEvaluation.bid_submission_id == submission_id)
        .order_by(BidderEvaluation.created_at.desc(), BidderEvaluation.id.desc())
    )
    evaluation = db.execute(stmt).scalars().first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No overall evaluation record found for submission {submission_id}.",
        )
    return evaluation


def get_submission_evaluation_detail(
    db: Session,
    submission_id: uuid.UUID,
    evaluation_id: Optional[uuid.UUID] = None,
) -> Tuple[BidderEvaluation, List[CriterionBreakdownItem]]:
    """Retrieve overall evaluation with full criterion breakdown."""
    if evaluation_id:
        evaluation = db.get(BidderEvaluation, evaluation_id)
        if not evaluation or evaluation.bid_submission_id != submission_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Overall evaluation {evaluation_id} not found for submission {submission_id}.",
            )
    else:
        evaluation = get_latest_submission_evaluation(db, submission_id)

    # Reconstruct breakdown from snapshot
    breakdown: List[CriterionBreakdownItem] = []
    snapshot = evaluation.rule_version_snapshot or {}
    criteria_list = snapshot.get("criteria", [])

    for c in criteria_list:
        breakdown.append(
            CriterionBreakdownItem(
                criterion_id=uuid.UUID(c["criterion_id"]),
                criterion_code=c["criterion_code"],
                criterion_name=c["criterion_name"],
                requirement_type=RequirementType(c["requirement_type"]),
                is_mandatory=c["is_mandatory"],
                result=EvaluationResult(c["result"]),
                has_evaluation=c.get("has_evaluation", True),
                evaluation_id=uuid.UUID(c["evaluation_id"]) if c.get("evaluation_id") else None,
                rule_version=c.get("rule_version"),
                explanation=c.get("explanation", {}),
                evidence_ids=c.get("evidence_ids", []),
            )
        )

    return evaluation, breakdown


def list_submission_evaluations_history(
    db: Session,
    submission_id: uuid.UUID,
) -> List[BidderEvaluation]:
    """List all historical evaluation runs for a submission in reverse chronological order."""
    submission = db.get(BidSubmission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission {submission_id} not found.",
        )

    stmt = (
        select(BidderEvaluation)
        .where(BidderEvaluation.bid_submission_id == submission_id)
        .order_by(BidderEvaluation.created_at.desc(), BidderEvaluation.id.desc())
    )
    return list(db.execute(stmt).scalars().all())
