"""Domain service for Phase 13 Human Review, Officer Override & Decision Audit."""

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import (
    CriterionEvaluation,
    EvaluationResult,
)
from app.db.models.evidence import Evidence
from app.db.models.review_case import (
    HumanDecision,
    OfficerDecision,
    ReviewAuditLog,
    ReviewCase,
    ReviewIssueType,
    ReviewItem,
    ReviewNote,
    ReviewPriority,
    ReviewStatus,
)
from app.db.models.tender_criterion import RequirementType, TenderCriterion
from app.db.models.user import User
from app.reviews.schemas import (
    EvidenceDetailItem,
    OfficerDecisionResponse,
    ReviewAuditLogResponse,
    ReviewCaseCreateRequest,
    ReviewCaseDetailResponse,
    ReviewNoteResponse,
)

logger = logging.getLogger("app.reviews.service")


def generate_review_cases_for_submission(
    db: Session,
    submission_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> List[ReviewCase]:
    """
    Scan a submission's criterion evaluations and create review cases for items
    that evaluated to MANUAL_REVIEW or contain conflicting/uncertain evidence.
    """
    submission = db.get(BidSubmission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission {submission_id} not found.",
        )

    tender_version = submission.tender_version
    tender_id = tender_version.tender_id
    tender_version_id = submission.tender_version_id
    bidder_id = submission.bidder_id

    # Latest overall evaluation
    overall_eval = (
        db.execute(
            select(BidderEvaluation)
            .where(BidderEvaluation.bid_submission_id == submission_id)
            .order_by(BidderEvaluation.created_at.desc(), BidderEvaluation.id.desc())
        )
        .scalars()
        .first()
    )

    # Fetch all criterion evaluations
    evals = (
        db.execute(
            select(CriterionEvaluation)
            .where(CriterionEvaluation.bid_submission_id == submission_id)
            .order_by(CriterionEvaluation.evaluated_at.desc())
        )
        .scalars()
        .all()
    )

    created_cases: List[ReviewCase] = []

    for eval_item in evals:
        # Check if criterion requires review
        if eval_item.result == EvaluationResult.MANUAL_REVIEW:
            # Check if an open review case already exists for this submission and criterion
            existing_case = (
                db.execute(
                    select(ReviewCase).where(
                        ReviewCase.bid_submission_id == submission_id,
                        ReviewCase.criterion_id == eval_item.criterion_id,
                        ReviewCase.status != ReviewStatus.RESOLVED,
                    )
                )
                .scalars()
                .first()
            )
            if existing_case:
                continue

            criterion = db.get(TenderCriterion, eval_item.criterion_id)
            crit_code = criterion.criterion_code if criterion else "UNKNOWN"
            is_mandatory = criterion and (
                criterion.requirement_type == RequirementType.MANDATORY or bool(criterion.mandatory)
            )

            priority = ReviewPriority.HIGH if is_mandatory else ReviewPriority.MEDIUM
            explanation_dict = eval_item.explanation or {}
            reason_text = (
                explanation_dict.get("reason")
                or str(explanation_dict.get("reasons", ["Manual review required."])[0])
                if explanation_dict.get("reasons")
                else "Manual review required by deterministic evaluation policy."
            )

            review_case = ReviewCase(
                tender_id=tender_id,
                tender_version_id=tender_version_id,
                bidder_id=bidder_id,
                bid_submission_id=submission_id,
                criterion_id=eval_item.criterion_id,
                criterion_evaluation_id=eval_item.id,
                overall_evaluation_id=overall_eval.id if overall_eval else None,
                evaluation_run_id=eval_item.evaluation_run_id,
                status=ReviewStatus.OPEN,
                priority=priority,
                issue_type=ReviewIssueType.MANUAL_REVIEW_REQUIRED,
                title=f"Manual Review Required: {crit_code}",
                description=reason_text,
                created_by=user_id,
            )
            db.add(review_case)
            db.flush()

            audit = ReviewAuditLog(
                review_case_id=review_case.id,
                action="AUTO_GENERATED",
                actor_id=user_id,
                details={
                    "criterion_code": crit_code,
                    "result": eval_item.result.value,
                    "priority": priority.value,
                },
            )
            db.add(audit)
            created_cases.append(review_case)

    db.commit()
    for c in created_cases:
        db.refresh(c)

    logger.info(
        "Auto-generated %d review cases for submission %s",
        len(created_cases),
        submission_id,
    )
    return created_cases


def create_manual_review_case(
    db: Session,
    payload: ReviewCaseCreateRequest,
    user_id: Optional[uuid.UUID] = None,
) -> ReviewCase:
    """Create a manual review case initiated by a procurement officer."""
    submission = db.get(BidSubmission, payload.bid_submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission {payload.bid_submission_id} not found.",
        )

    tender_id = submission.tender_version.tender_id
    tender_version_id = submission.tender_version_id
    bidder_id = submission.bidder_id

    review_case = ReviewCase(
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        bidder_id=bidder_id,
        bid_submission_id=payload.bid_submission_id,
        criterion_id=payload.criterion_id,
        criterion_evaluation_id=payload.criterion_evaluation_id,
        status=ReviewStatus.OPEN,
        priority=payload.priority,
        issue_type=payload.issue_type,
        title=payload.title,
        description=payload.description,
        created_by=user_id,
    )
    db.add(review_case)
    db.flush()

    audit = ReviewAuditLog(
        review_case_id=review_case.id,
        action="CREATED",
        actor_id=user_id,
        details={
            "title": payload.title,
            "issue_type": payload.issue_type.value,
            "priority": payload.priority.value,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(review_case)
    return review_case


def list_review_cases(
    db: Session,
    status_filter: Optional[ReviewStatus] = None,
    priority_filter: Optional[ReviewPriority] = None,
    issue_type_filter: Optional[ReviewIssueType] = None,
    tender_id: Optional[uuid.UUID] = None,
    tender_version_id: Optional[uuid.UUID] = None,
    bidder_id: Optional[uuid.UUID] = None,
    submission_id: Optional[uuid.UUID] = None,
    assigned_to: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[int, List[ReviewCase]]:
    """List review cases with optional filters and pagination."""
    stmt = select(ReviewCase)

    if status_filter:
        stmt = stmt.where(ReviewCase.status == status_filter)
    if priority_filter:
        stmt = stmt.where(ReviewCase.priority == priority_filter)
    if issue_type_filter:
        stmt = stmt.where(ReviewCase.issue_type == issue_type_filter)
    if tender_id:
        stmt = stmt.where(ReviewCase.tender_id == tender_id)
    if tender_version_id:
        stmt = stmt.where(ReviewCase.tender_version_id == tender_version_id)
    if bidder_id:
        stmt = stmt.where(ReviewCase.bidder_id == bidder_id)
    if submission_id:
        stmt = stmt.where(ReviewCase.bid_submission_id == submission_id)
    if assigned_to:
        stmt = stmt.where(ReviewCase.assigned_to == assigned_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    items_stmt = stmt.order_by(ReviewCase.created_at.desc()).offset(skip).limit(limit)
    items = list(db.execute(items_stmt).scalars().all())

    return total, items


def get_review_case_detail(
    db: Session,
    review_id: uuid.UUID,
) -> ReviewCaseDetailResponse:
    """Retrieve full review case details, evidence bounding boxes, OPA output, and decisions."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    # Gather evidence items
    evidence_details: List[EvidenceDetailItem] = []
    if review.criterion_id and review.bid_submission_id:
        ev_stmt = select(Evidence).where(
            Evidence.bid_submission_id == review.bid_submission_id,
            Evidence.criterion_id == review.criterion_id,
        )
        evidence_records = list(db.execute(ev_stmt).scalars().all())
        for ev in evidence_records:
            evidence_details.append(
                EvidenceDetailItem(
                    evidence_id=ev.id,
                    document_id=ev.document_id,
                    document_filename=ev.document.filename if ev.document else None,
                    status=ev.status.value,
                    extracted_value=ev.raw_extracted_data or {"value": ev.extracted_value, "text": ev.extracted_text},
                    confidence=ev.confidence,
                    source_page=ev.source_page,
                    source_block_id=ev.source_block_id,
                    source_table_reference=ev.source_table_reference,
                    bounding_box=ev.bbox,
                    extractor_version=ev.extractor_version,
                )
            )

    # Gather related models
    tender = review.tender
    bidder = review.bidder
    submission = review.bid_submission
    criterion = review.criterion
    crit_eval = review.criterion_evaluation
    overall_eval = review.overall_evaluation

    return ReviewCaseDetailResponse(
        id=review.id,
        tender_id=review.tender_id,
        tender_version_id=review.tender_version_id,
        bidder_id=review.bidder_id,
        bid_submission_id=review.bid_submission_id,
        criterion_id=review.criterion_id,
        criterion_evaluation_id=review.criterion_evaluation_id,
        overall_evaluation_id=review.overall_evaluation_id,
        evaluation_run_id=review.evaluation_run_id,
        status=review.status,
        priority=review.priority,
        issue_type=review.issue_type,
        title=review.title,
        description=review.description,
        assigned_to=review.assigned_to,
        created_by=review.created_by,
        created_at=review.created_at,
        updated_at=review.updated_at,
        resolved_at=review.resolved_at,
        tender_number=tender.tender_number if tender else None,
        bidder_name=bidder.legal_name if bidder else None,
        submission_reference=submission.submission_reference if submission else None,
        criterion_code=criterion.criterion_code if criterion else None,
        criterion_name=criterion.name if criterion else None,
        criterion_requirement_type=criterion.requirement_type.value if criterion else None,
        system_criterion_result=crit_eval.result if crit_eval else None,
        system_overall_result=overall_eval.result if overall_eval else None,
        opa_explanation=crit_eval.explanation if crit_eval else {},
        evidence_items=evidence_details,
        decisions=[OfficerDecisionResponse.model_validate(d) for d in review.decisions],
        notes=[ReviewNoteResponse.model_validate(n) for n in review.notes],
        audit_logs=[ReviewAuditLogResponse.model_validate(a) for a in review.audit_logs],
    )


def assign_review_case(
    db: Session,
    review_id: uuid.UUID,
    assignee_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ReviewCase:
    """Assign a review case to an authorized user."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    assignee = db.get(User, assignee_id)
    if not assignee or not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assignee user {assignee_id} is invalid or inactive.",
        )

    review.assigned_to = assignee_id
    if review.status == ReviewStatus.OPEN:
        review.status = ReviewStatus.IN_REVIEW

    audit = ReviewAuditLog(
        review_case_id=review.id,
        action="ASSIGNED",
        actor_id=actor_id,
        details={"assigned_to": str(assignee_id), "assignee_email": assignee.email},
    )
    db.add(audit)
    db.commit()
    db.refresh(review)
    return review


def record_officer_decision(
    db: Session,
    review_id: uuid.UUID,
    decision: HumanDecision,
    reason: str,
    final_verdict: Optional[EvaluationResult],
    officer_id: uuid.UUID,
) -> OfficerDecision:
    """
    Record an explicit human decision (CONFIRM, OVERRIDE, REQUEST_REVIEW).
    Strictly preserves automated system results and stores officer justification.
    """
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    if not reason or not reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty justification reason is strictly required.",
        )

    if decision == HumanDecision.OVERRIDE:
        if not final_verdict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An override decision must specify a final_verdict (ELIGIBLE, NOT_ELIGIBLE, MANUAL_REVIEW).",
            )

    # Determine system result
    system_result = EvaluationResult.MANUAL_REVIEW
    if review.criterion_evaluation:
        system_result = review.criterion_evaluation.result
    elif review.overall_evaluation:
        system_result = review.overall_evaluation.result

    decision_record = OfficerDecision(
        review_case_id=review.id,
        criterion_id=review.criterion_id,
        criterion_evaluation_id=review.criterion_evaluation_id,
        decision=decision,
        system_result=system_result,
        final_verdict=final_verdict or system_result,
        reason=reason.strip(),
        officer_id=officer_id,
    )
    db.add(decision_record)

    # Update review status
    if review.status == ReviewStatus.OPEN:
        review.status = ReviewStatus.IN_REVIEW

    audit = ReviewAuditLog(
        review_case_id=review.id,
        action="DECISION_RECORDED",
        actor_id=officer_id,
        details={
            "decision": decision.value,
            "system_result": system_result.value,
            "final_verdict": final_verdict.value if final_verdict else system_result.value,
            "reason": reason.strip(),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(decision_record)
    return decision_record


def add_review_note(
    db: Session,
    review_id: uuid.UUID,
    note_text: str,
    author_id: uuid.UUID,
) -> ReviewNote:
    """Add an immutable review note."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    if not note_text or not note_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note content cannot be empty.",
        )

    note = ReviewNote(
        review_case_id=review.id,
        author_id=author_id,
        note=note_text.strip(),
    )
    db.add(note)
    db.flush()

    audit = ReviewAuditLog(
        review_case_id=review.id,
        action="NOTE_ADDED",
        actor_id=author_id,
        details={"note_id": str(note.id)},
    )
    db.add(audit)
    db.commit()
    db.refresh(note)
    return note


def resolve_review_case(
    db: Session,
    review_id: uuid.UUID,
    officer_id: uuid.UUID,
) -> ReviewCase:
    """Resolve a review case. Requires at least one recorded officer decision."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    if not review.decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resolve review case without an explicit officer decision recorded.",
        )

    review.status = ReviewStatus.RESOLVED
    review.resolved_at = datetime.datetime.now(datetime.timezone.utc)

    audit = ReviewAuditLog(
        review_case_id=review.id,
        action="RESOLVED",
        actor_id=officer_id,
        details={"resolved_at": review.resolved_at.isoformat()},
    )
    db.add(audit)
    db.commit()
    db.refresh(review)
    return review


def reopen_review_case(
    db: Session,
    review_id: uuid.UUID,
    officer_id: uuid.UUID,
) -> ReviewCase:
    """Reopen a previously resolved review case."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    if review.status != ReviewStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reopen review case with status {review.status.value}.",
        )

    review.status = ReviewStatus.IN_REVIEW
    review.resolved_at = None

    audit = ReviewAuditLog(
        review_case_id=review.id,
        action="REOPENED",
        actor_id=officer_id,
        details={},
    )
    db.add(audit)
    db.commit()
    db.refresh(review)
    return review


def get_review_history(
    db: Session,
    review_id: uuid.UUID,
) -> List[ReviewAuditLog]:
    """Retrieve full chronological audit trail for a review case."""
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review case {review_id} not found.",
        )

    stmt = (
        select(ReviewAuditLog)
        .where(ReviewAuditLog.review_case_id == review_id)
        .order_by(ReviewAuditLog.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())
