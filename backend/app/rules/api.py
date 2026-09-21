"""FastAPI REST API routes for deterministic rule configuration and OPA evaluation."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.user import User
from app.db.session import get_db
from app.rules.schemas import (
    CriterionEvaluationResponse,
    CriterionRuleResponse,
    RuleCreateRequest,
    SubmissionEvaluationsListResponse,
)
from app.rules.service import (
    evaluate_submission_criterion,
    get_criterion_rule,
    get_or_create_criterion_rule,
    get_submission_criterion_evaluation,
    list_submission_evaluations,
)

router = APIRouter(tags=["Deterministic Rule Engine & OPA"])


@router.post(
    "/criteria/{criterion_id}/rule",
    response_model=CriterionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or customize deterministic evaluation rule for approved criterion",
)
def create_or_update_rule_endpoint(
    criterion_id: uuid.UUID,
    payload: Optional[RuleCreateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
) -> CriterionRuleResponse:
    """Configure or generate a deterministic OPA rule for an officer-approved criterion."""
    rule_type = payload.rule_type if payload else None
    config = payload.configuration if payload else None

    rule = get_or_create_criterion_rule(
        db=db,
        criterion_id=criterion_id,
        user_id=current_user.id,
        rule_type=rule_type,
        configuration=config,
    )
    return CriterionRuleResponse.model_validate(rule)


@router.get(
    "/criteria/{criterion_id}/rule",
    response_model=CriterionRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active deterministic rule for a criterion",
)
def get_rule_endpoint(
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> CriterionRuleResponse:
    """Retrieve active deterministic rule configuration for a tender criterion."""
    rule = get_or_create_criterion_rule(db=db, criterion_id=criterion_id, user_id=current_user.id)
    return CriterionRuleResponse.model_validate(rule)


@router.post(
    "/submissions/{submission_id}/criteria/{criterion_id}/evaluate",
    response_model=CriterionEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute deterministic OPA evaluation for a criterion",
)
def evaluate_criterion_endpoint(
    submission_id: uuid.UUID,
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> CriterionEvaluationResponse:
    """
    Evaluate structured bidder evidence against the criterion's deterministic rule in OPA.
    Returns immutable evaluation outcome (ELIGIBLE, NOT_ELIGIBLE, MANUAL_REVIEW).
    """
    evaluation = evaluate_submission_criterion(
        db=db,
        submission_id=submission_id,
        criterion_id=criterion_id,
        user_id=current_user.id,
    )
    return CriterionEvaluationResponse.model_validate(evaluation)


@router.get(
    "/submissions/{submission_id}/criteria/{criterion_id}/evaluation",
    response_model=CriterionEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest evaluation record for submission criterion",
)
def get_evaluation_endpoint(
    submission_id: uuid.UUID,
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> CriterionEvaluationResponse:
    """Retrieve the latest evaluation result and input snapshot for a submission's criterion."""
    evaluation = get_submission_criterion_evaluation(
        db=db,
        submission_id=submission_id,
        criterion_id=criterion_id,
    )
    return CriterionEvaluationResponse.model_validate(evaluation)


@router.get(
    "/submissions/{submission_id}/evaluations",
    response_model=SubmissionEvaluationsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all criterion evaluations for a bidder submission",
)
def list_submission_evaluations_endpoint(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> SubmissionEvaluationsListResponse:
    """List all criterion evaluations generated for a bidder submission."""
    items = list_submission_evaluations(db=db, submission_id=submission_id)
    return SubmissionEvaluationsListResponse(
        submission_id=submission_id,
        total_evaluations=len(items),
        evaluations=[CriterionEvaluationResponse.model_validate(e) for e in items],
    )
