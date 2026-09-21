"""Officer approval and tender criterion version control domain service."""

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.approval.schemas import (
    CriterionApprovalRequest,
    CriterionCorrectionRequest,
    CriterionRejectionRequest,
)
from app.db.models.criterion_approval_history import (
    ApprovalAction,
    CriterionApprovalHistory,
)
from app.db.models.tender import Tender
from app.db.models.tender_criterion import (
    ApprovalStatus,
    ExtractionStatus,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User

logger = logging.getLogger("app.approval.service")


def get_criterion_for_officer_action(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    for_update: bool = False,
) -> TenderCriterion:
    """
    Retrieve and validate that a criterion belongs strictly to the given tender and tender version.
    Optionally applies row-level locking for concurrency safety.
    """
    bind = db.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    stmt = (
        select(TenderCriterion)
        .join(TenderVersion, TenderCriterion.tender_version_id == TenderVersion.id)
        .where(
            TenderCriterion.id == criterion_id,
            TenderCriterion.tender_version_id == tender_version_id,
            TenderVersion.tender_id == tender_id,
        )
    )

    if for_update and not is_sqlite:
        stmt = stmt.with_for_update()

    criterion = db.execute(stmt).scalar_one_or_none()
    if not criterion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion '{criterion_id}' not found for Tender '{tender_id}' and Version '{tender_version_id}'.",
        )
    return criterion


def correct_criterion(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    correction: CriterionCorrectionRequest,
    current_user: User,
) -> TenderCriterion:
    """
    Apply officer corrections to working criterion fields without modifying original AI extraction values.
    Leaves approval_status in PENDING_REVIEW and records audit diff.
    """
    criterion = get_criterion_for_officer_action(
        db=db,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        criterion_id=criterion_id,
        for_update=True,
    )

    changed_fields: Dict[str, Dict[str, Any]] = {}
    updates = correction.model_dump(exclude_unset=True)
    reason = updates.pop("reason", None)

    for field, new_val in updates.items():
        if not hasattr(criterion, field):
            continue
        old_val = getattr(criterion, field)
        if old_val != new_val:
            changed_fields[field] = {"old": old_val, "new": new_val}
            setattr(criterion, field, new_val)

    if not changed_fields:
        return criterion

    criterion.is_corrected = True
    criterion.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # Record audit event
    prev_status = criterion.approval_status
    history = CriterionApprovalHistory(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        action=ApprovalAction.CORRECT,
        previous_status=prev_status.value if hasattr(prev_status, "value") else str(prev_status),
        new_status=ApprovalStatus.PENDING_REVIEW.value,
        changed_fields=changed_fields,
        reason=reason,
        officer_id=current_user.id,
    )
    db.add(history)

    # Ensure status stays PENDING_REVIEW after correction
    criterion.approval_status = ApprovalStatus.PENDING_REVIEW

    try:
        db.commit()
        db.refresh(criterion)
        logger.info(
            "Officer %s corrected criterion %s (fields=%s)",
            current_user.id,
            criterion.id,
            list(changed_fields.keys()),
        )
        return criterion
    except Exception as exc:
        db.rollback()
        logger.error("Failed to commit criterion correction: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record criterion correction.",
        )


def approve_criterion(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    current_user: User,
    approval_data: Optional[CriterionApprovalRequest] = None,
) -> TenderCriterion:
    """
    Explicitly approve a candidate criterion, promoting it to official requirement for this tender version.
    """
    criterion = get_criterion_for_officer_action(
        db=db,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        criterion_id=criterion_id,
        for_update=True,
    )

    if criterion.extraction_status == ExtractionStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve a criterion whose extraction failed.",
        )

    prev_status = criterion.approval_status
    now = datetime.datetime.now(datetime.timezone.utc)
    reason = approval_data.reason if approval_data else None

    criterion.approval_status = ApprovalStatus.APPROVED
    criterion.approved_by = current_user.id
    criterion.approved_at = now
    criterion.rejection_reason = None
    criterion.updated_at = now

    history = CriterionApprovalHistory(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        action=ApprovalAction.APPROVE,
        previous_status=prev_status.value if hasattr(prev_status, "value") else str(prev_status),
        new_status=ApprovalStatus.APPROVED.value,
        changed_fields={"approval_status": {"old": str(prev_status), "new": "APPROVED"}},
        reason=reason,
        officer_id=current_user.id,
    )
    db.add(history)

    try:
        db.commit()
        db.refresh(criterion)
        logger.info(
            "Officer %s approved criterion %s (code=%s)",
            current_user.id,
            criterion.id,
            criterion.criterion_code,
        )
        return criterion
    except Exception as exc:
        db.rollback()
        logger.error("Failed to approve criterion %s: %s", criterion.id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record criterion approval.",
        )


def reject_criterion(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    current_user: User,
    rejection_data: CriterionRejectionRequest,
) -> TenderCriterion:
    """
    Explicitly reject a candidate criterion with a mandatory justification reason.
    """
    if not rejection_data.reason or not rejection_data.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty justification reason is mandatory to reject a criterion.",
        )

    criterion = get_criterion_for_officer_action(
        db=db,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        criterion_id=criterion_id,
        for_update=True,
    )

    prev_status = criterion.approval_status
    now = datetime.datetime.now(datetime.timezone.utc)
    reason = rejection_data.reason.strip()

    criterion.approval_status = ApprovalStatus.REJECTED
    criterion.rejection_reason = reason
    criterion.approved_by = None
    criterion.approved_at = None
    criterion.updated_at = now

    history = CriterionApprovalHistory(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        action=ApprovalAction.REJECT,
        previous_status=prev_status.value if hasattr(prev_status, "value") else str(prev_status),
        new_status=ApprovalStatus.REJECTED.value,
        changed_fields={"approval_status": {"old": str(prev_status), "new": "REJECTED"}},
        reason=reason,
        officer_id=current_user.id,
    )
    db.add(history)

    try:
        db.commit()
        db.refresh(criterion)
        logger.info(
            "Officer %s rejected criterion %s (code=%s, reason=%s)",
            current_user.id,
            criterion.id,
            criterion.criterion_code,
            reason,
        )
        return criterion
    except Exception as exc:
        db.rollback()
        logger.error("Failed to reject criterion %s: %s", criterion.id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record criterion rejection.",
        )


def get_criterion_approval_history(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
) -> List[CriterionApprovalHistory]:
    """Retrieve chronological audit history of officer reviews for a criterion."""
    # Validate criterion exists under tender version
    get_criterion_for_officer_action(
        db=db,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        criterion_id=criterion_id,
    )

    stmt = (
        select(CriterionApprovalHistory)
        .where(CriterionApprovalHistory.criterion_id == criterion_id)
        .order_by(CriterionApprovalHistory.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_approved_criteria(
    db: Session,
    tender_version_id: uuid.UUID,
) -> List[TenderCriterion]:
    """
    Authoritative query returning strictly APPROVED criteria for a specific tender version.
    This provides the verified baseline consumed by future evaluation and rule engines.
    """
    stmt = (
        select(TenderCriterion)
        .where(
            TenderCriterion.tender_version_id == tender_version_id,
            TenderCriterion.approval_status == ApprovalStatus.APPROVED,
        )
        .order_by(TenderCriterion.criterion_code.asc())
    )
    return list(db.execute(stmt).scalars().all())
