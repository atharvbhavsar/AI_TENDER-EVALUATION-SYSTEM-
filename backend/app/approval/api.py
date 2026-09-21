"""API router for Officer Approval and Criterion Version Control."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.approval.schemas import (
    CriterionApprovalHistoryResponse,
    CriterionApprovalRequest,
    CriterionCorrectionRequest,
    CriterionRejectionRequest,
)
from app.approval.service import (
    approve_criterion,
    correct_criterion,
    get_criterion_approval_history,
    reject_criterion,
)
from app.auth.dependencies import require_permissions
from app.db.models.user import User
from app.db.session import get_db
from app.extraction.schemas import TenderCriterionResponse

router = APIRouter(prefix="/tenders/{tender_id}/versions/{version_id}/criteria", tags=["Officer Criterion Approval"])


@router.patch(
    "/{criterion_id}",
    response_model=TenderCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Correct Candidate Criterion Fields",
)
def correct_criterion_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    correction: CriterionCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_APPROVE")),
) -> TenderCriterionResponse:
    """
    Apply officer corrections to candidate criterion fields.
    Preserves original AI extraction snapshot and leaves approval status in PENDING_REVIEW.
    """
    updated = correct_criterion(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        criterion_id=criterion_id,
        correction=correction,
        current_user=current_user,
    )
    return TenderCriterionResponse.model_validate(updated)


@router.post(
    "/{criterion_id}/approve",
    response_model=TenderCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Candidate Criterion",
)
def approve_criterion_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    approval_data: Optional[CriterionApprovalRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_APPROVE")),
) -> TenderCriterionResponse:
    """
    Explicitly approve a candidate criterion, promoting it to official requirement for this tender version.
    """
    approved = approve_criterion(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        criterion_id=criterion_id,
        current_user=current_user,
        approval_data=approval_data,
    )
    return TenderCriterionResponse.model_validate(approved)


@router.post(
    "/{criterion_id}/reject",
    response_model=TenderCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Candidate Criterion",
)
def reject_criterion_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    rejection_data: CriterionRejectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_APPROVE")),
) -> TenderCriterionResponse:
    """
    Explicitly reject a candidate criterion with a mandatory justification reason.
    """
    rejected = reject_criterion(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        criterion_id=criterion_id,
        current_user=current_user,
        rejection_data=rejection_data,
    )
    return TenderCriterionResponse.model_validate(rejected)


@router.get(
    "/{criterion_id}/history",
    response_model=List[CriterionApprovalHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Criterion Review and Approval Audit History",
)
def get_criterion_history_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> List[CriterionApprovalHistoryResponse]:
    """Retrieve chronological audit trail of officer reviews, corrections, and status transitions."""
    history = get_criterion_approval_history(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        criterion_id=criterion_id,
    )
    return [CriterionApprovalHistoryResponse.model_validate(h) for h in history]
