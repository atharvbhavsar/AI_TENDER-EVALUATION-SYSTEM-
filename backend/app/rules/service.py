"""Domain service for deterministic rule generation and OPA evaluation."""

import asyncio
import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.bid_submission import BidSubmission
from app.db.models.criterion_evaluation import (
    CriterionEvaluation,
    EvaluationResult,
)
from app.db.models.criterion_rule import (
    CriterionRule,
    RuleStatus,
    RuleType,
)
from app.db.models.evidence import Evidence
from app.db.models.tender_criterion import ApprovalStatus, TenderCriterion
from app.rules.normalizers import (
    normalize_numeric_amount_to_base,
    standardize_currency_code,
)
from app.rules.opa.base import BaseOPAClient
from app.rules.opa.client import get_opa_client
from app.rules.templates import infer_rule_template_from_criterion

logger = logging.getLogger("app.rules.service")


def get_or_create_criterion_rule(
    db: Session,
    criterion_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    rule_type: Optional[RuleType] = None,
    configuration: Optional[Dict[str, Any]] = None,
) -> CriterionRule:
    """
    Generate or configure a deterministic evaluation rule for an APPROVED tender criterion.
    Strictly forbids rule creation for unapproved candidate criteria.
    """
    settings = get_settings()
    crit = db.get(TenderCriterion, criterion_id)
    if not crit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion {criterion_id} not found.",
        )

    # Strict Rule: Only APPROVED criteria can have evaluation rules
    if crit.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Criterion {criterion_id} is in status '{crit.approval_status}'. Rules can only be created for APPROVED criteria.",
        )

    # Check for existing active rule
    existing_rule = db.execute(
        select(CriterionRule).where(
            CriterionRule.criterion_id == criterion_id,
            CriterionRule.status == RuleStatus.ACTIVE,
        )
    ).scalar_one_or_none()

    if existing_rule:
        if configuration or rule_type:
            if rule_type:
                existing_rule.rule_type = rule_type
            if configuration:
                existing_rule.configuration = configuration
            db.commit()
            db.refresh(existing_rule)
        return existing_rule

    # Infer template if not explicitly specified
    if not rule_type or not configuration:
        inferred_type, inferred_config = infer_rule_template_from_criterion(crit)
        final_type = rule_type or inferred_type
        final_config = configuration or inferred_config
    else:
        final_type = rule_type
        final_config = configuration

    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        tender_version_id=crit.tender_version_id,
        rule_type=final_type,
        rule_version=settings.DEFAULT_POLICY_VERSION,
        template_version="v1.0",
        rego_policy_reference=settings.OPA_POLICY_PACKAGE,
        configuration=final_config,
        status=RuleStatus.ACTIVE if final_type != RuleType.UNSUPPORTED else RuleStatus.UNSUPPORTED,
        created_by=user_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info("Created rule %s (%s) for criterion %s", rule.id, rule.rule_type, criterion_id)
    return rule


def get_criterion_rule(db: Session, criterion_id: uuid.UUID) -> CriterionRule:
    """Retrieve active rule for a criterion."""
    rule = db.execute(
        select(CriterionRule).where(
            CriterionRule.criterion_id == criterion_id,
            CriterionRule.status == RuleStatus.ACTIVE,
        )
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active rule found for criterion {criterion_id}.",
        )
    return rule


def evaluate_submission_criterion(
    db: Session,
    submission_id: uuid.UUID,
    criterion_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    opa_client: Optional[BaseOPAClient] = None,
    evaluation_run_id: Optional[uuid.UUID] = None,
) -> CriterionEvaluation:
    """
    Execute deterministic OPA evaluation for a specific approved criterion against bidder evidence:
    1. Validates submission and tender version scope.
    2. Verifies criterion is strictly APPROVED.
    3. Loads or creates active rule for the criterion.
    4. Fetches validated evidence items from Phase 9.
    5. Formats structured OPA input payload.
    6. Calls OPA / Rego deterministic policy engine.
    7. Validates decision (ELIGIBLE, NOT_ELIGIBLE, MANUAL_REVIEW).
    8. Persists immutable CriterionEvaluation record with input snapshot.
    """
    settings = get_settings()
    opa_client = opa_client or get_opa_client()

    sub = db.get(BidSubmission, submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )

    crit = db.get(TenderCriterion, criterion_id)
    if not crit or crit.tender_version_id != sub.tender_version_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion {criterion_id} not found for tender version {sub.tender_version_id}.",
        )

    if crit.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Criterion {criterion_id} is in status '{crit.approval_status}'. Only APPROVED criteria can be evaluated.",
        )

    # 1. Fetch or generate rule
    rule = get_or_create_criterion_rule(db=db, criterion_id=criterion_id, user_id=user_id)

    # 2. Fetch validated evidence records
    ev_stmt = select(Evidence).where(
        Evidence.bid_submission_id == submission_id,
        Evidence.criterion_id == criterion_id,
    ).order_by(Evidence.created_at.asc())
    evidence_items = db.execute(ev_stmt).scalars().all()

    # 3. Format structured OPA input
    evidence_payload: List[Dict[str, Any]] = []
    evidence_ids: List[str] = []

    for ev in evidence_items:
        evidence_ids.append(str(ev.id))
        evidence_payload.append({
            "id": str(ev.id),
            "status": ev.status.value,
            "evidence_type": ev.evidence_type,
            "extracted_text": ev.extracted_text or "",
            "extracted_value": ev.extracted_value,
            "normalized_value": ev.normalized_value,
            "unit": ev.unit,
            "currency": standardize_currency_code(ev.currency),
            "period": ev.period,
            "date_value": ev.date_value,
            "certificate_data": ev.certificate_data or {},
            "experience_data": ev.experience_data or {},
            "confidence": ev.confidence,
        })

    rule_config_copy = dict(rule.configuration)
    rule_config_copy["rule_type"] = rule.rule_type.value
    rule_config_copy["rule_version"] = rule.rule_version
    rule_config_copy["min_confidence"] = rule_config_copy.get("min_confidence", settings.MIN_EVALUATION_CONFIDENCE)

    opa_input = {
        "rule": rule_config_copy,
        "criterion": {
            "criterion_id": str(crit.id),
            "criterion_code": crit.criterion_code,
            "name": crit.name,
            "requirement_type": crit.requirement_type.value,
            "category": crit.category.value,
        },
        "evidence": evidence_payload,
    }

    # 4. Call OPA
    try:
        opa_resp = asyncio.run(
            opa_client.evaluate_policy(
                policy_path=rule.rego_policy_reference,
                input_data=opa_input,
            )
        )
    except Exception as exc:
        logger.error("OPA evaluation error: %s", str(exc))
        opa_resp = {
            "result": EvaluationResult.MANUAL_REVIEW.value,
            "explanation": {"reason": f"OPA policy execution error: {str(exc)}"},
        }

    # 5. Validate OPA response
    raw_result = opa_resp.get("result", EvaluationResult.MANUAL_REVIEW.value)
    if raw_result not in (EvaluationResult.ELIGIBLE.value, EvaluationResult.NOT_ELIGIBLE.value, EvaluationResult.MANUAL_REVIEW.value):
        raw_result = EvaluationResult.MANUAL_REVIEW.value

    final_result = EvaluationResult(raw_result)
    explanation = opa_resp.get("explanation", {})

    # 6. Persist immutable evaluation record
    evaluation = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        bidder_id=sub.bidder_id,
        bid_submission_id=sub.id,
        tender_version_id=sub.tender_version_id,
        rule_id=rule.id,
        rule_version=rule.rule_version,
        policy_version=settings.DEFAULT_POLICY_VERSION,
        result=final_result,
        input_snapshot=opa_input,
        evidence_ids=evidence_ids,
        explanation=explanation,
        evaluation_run_id=evaluation_run_id,
        evaluated_by=user_id,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    logger.info(
        "Evaluated criterion %s for submission %s -> %s",
        crit.criterion_code,
        submission_id,
        final_result.value,
    )
    return evaluation


def get_submission_criterion_evaluation(
    db: Session,
    submission_id: uuid.UUID,
    criterion_id: uuid.UUID,
) -> CriterionEvaluation:
    """Retrieve the latest evaluation record for a submission's criterion."""
    stmt = (
        select(CriterionEvaluation)
        .where(
            CriterionEvaluation.bid_submission_id == submission_id,
            CriterionEvaluation.criterion_id == criterion_id,
        )
        .order_by(CriterionEvaluation.evaluated_at.desc())
    )
    evaluation = db.execute(stmt).scalars().first()
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation record found for criterion {criterion_id} in submission {submission_id}.",
        )
    return evaluation


def list_submission_evaluations(
    db: Session,
    submission_id: uuid.UUID,
) -> List[CriterionEvaluation]:
    """List all latest criterion evaluations for a submission."""
    sub = db.get(BidSubmission, submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )

    stmt = (
        select(CriterionEvaluation)
        .where(CriterionEvaluation.bid_submission_id == submission_id)
        .order_by(CriterionEvaluation.evaluated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
