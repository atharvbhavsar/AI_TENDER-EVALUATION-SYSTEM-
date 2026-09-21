"""FastAPI REST routes for Phase 12 bidder-level overall eligibility aggregation."""

import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.aggregation import service
from app.aggregation.schemas import (
    BidderEvaluationDetailResponse,
    BidderEvaluationResponse,
    EvaluateSubmissionRequest,
    EvaluationHistoryListResponse,
    SubmissionCriteriaBreakdownResponse,
)
from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.user import User
from app.db.session import get_db

logger = logging.getLogger("app.aggregation.api")

router = APIRouter(tags=["Bidder Aggregation & Overall Eligibility"])


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=BidderEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Aggregate and evaluate overall bidder eligibility",
)
def evaluate_submission_endpoint(
    submission_id: uuid.UUID,
    payload: Optional[EvaluateSubmissionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """
    Deterministically aggregate all approved criterion evaluations for a bidder submission
    and compute the overall eligibility result (ELIGIBLE, NOT_ELIGIBLE, MANUAL_REVIEW).
    """
    policy_version = payload.aggregation_policy_version if payload else "v1.0"
    evaluation_run_id = payload.evaluation_run_id if payload else None
    run_rules = payload.run_rules if payload else False
    auto_generate_reviews = payload.auto_generate_reviews if payload else False

    return service.aggregate_submission_evaluation(
        db=db,
        submission_id=submission_id,
        user_id=current_user.id,
        policy_version=policy_version,
        evaluation_run_id=evaluation_run_id,
        run_rules=run_rules,
        auto_generate_reviews=auto_generate_reviews,
    )


@router.get(
    "/submissions/{submission_id}/evaluation",
    response_model=BidderEvaluationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest overall evaluation for a submission",
)
def get_submission_overall_evaluation_endpoint(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Retrieve the latest aggregated overall evaluation along with criterion breakdown."""
    evaluation, breakdown = service.get_submission_evaluation_detail(
        db=db,
        submission_id=submission_id,
    )
    return BidderEvaluationDetailResponse(
        id=evaluation.id,
        tender_id=evaluation.tender_id,
        tender_version_id=evaluation.tender_version_id,
        bidder_id=evaluation.bidder_id,
        bid_submission_id=evaluation.bid_submission_id,
        evaluation_run_id=evaluation.evaluation_run_id,
        result=evaluation.result,
        aggregation_policy_version=evaluation.aggregation_policy_version,
        criterion_count=evaluation.criterion_count,
        eligible_count=evaluation.eligible_count,
        not_eligible_count=evaluation.not_eligible_count,
        manual_review_count=evaluation.manual_review_count,
        mandatory_criterion_count=evaluation.mandatory_criterion_count,
        mandatory_eligible_count=evaluation.mandatory_eligible_count,
        mandatory_not_eligible_count=evaluation.mandatory_not_eligible_count,
        mandatory_manual_review_count=evaluation.mandatory_manual_review_count,
        optional_criterion_count=evaluation.optional_criterion_count,
        optional_eligible_count=evaluation.optional_eligible_count,
        optional_not_eligible_count=evaluation.optional_not_eligible_count,
        optional_manual_review_count=evaluation.optional_manual_review_count,
        explanation=evaluation.explanation,
        evaluated_by=evaluation.evaluated_by,
        created_at=evaluation.created_at,
        criteria_breakdown=breakdown,
        rule_version_snapshot=evaluation.rule_version_snapshot,
    )


@router.get(
    "/submissions/{submission_id}/evaluation/criteria",
    response_model=SubmissionCriteriaBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Get criterion evaluation breakdown for a submission",
)
def get_submission_criteria_breakdown_endpoint(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Retrieve individual criterion results for a submission's latest overall evaluation."""
    evaluation, breakdown = service.get_submission_evaluation_detail(
        db=db,
        submission_id=submission_id,
    )
    return SubmissionCriteriaBreakdownResponse(
        bid_submission_id=submission_id,
        evaluation_id=evaluation.id,
        evaluation_run_id=evaluation.evaluation_run_id,
        overall_result=evaluation.result,
        criteria=breakdown,
    )


@router.get(
    "/submissions/{submission_id}/evaluations/history",
    response_model=EvaluationHistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List historical overall evaluation runs for a submission",
)
def list_submission_evaluations_history_endpoint(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """List all historical overall evaluation runs for a submission."""
    evaluations = service.list_submission_evaluations_history(
        db=db,
        submission_id=submission_id,
    )
    return EvaluationHistoryListResponse(
        bid_submission_id=submission_id,
        total_runs=len(evaluations),
        evaluations=[BidderEvaluationResponse.model_validate(e) for e in evaluations],
    )
