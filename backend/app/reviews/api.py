"""FastAPI REST endpoints for Phase 13 Human Review, Officer Override & Decision Audit."""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.review_case import (
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
from app.db.models.user import User
from app.db.session import get_db
from app.reviews import service
from app.reviews.schemas import (
    OfficerDecisionCreateRequest,
    OfficerDecisionResponse,
    ReviewAssignRequest,
    ReviewAuditLogResponse,
    ReviewCaseCreateRequest,
    ReviewCaseDetailResponse,
    ReviewCaseListResponse,
    ReviewCaseResponse,
    ReviewNoteCreateRequest,
    ReviewNoteResponse,
)

logger = logging.getLogger("app.reviews.api")

router = APIRouter(prefix="/reviews", tags=["Human Review & Officer Decisions"])


@router.post(
    "/generate",
    response_model=List[ReviewCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Auto-generate review cases for a submission",
)
def generate_review_cases_endpoint(
    submission_id: uuid.UUID = Query(..., description="ID of the bidder submission"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_CREATE")),
):
    """Scan submission criterion evaluations and automatically create review cases for MANUAL_REVIEW items."""
    cases = service.generate_review_cases_for_submission(
        db=db,
        submission_id=submission_id,
        user_id=current_user.id,
    )
    return [ReviewCaseResponse.model_validate(c) for c in cases]


@router.post(
    "",
    response_model=ReviewCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual review case",
)
def create_manual_review_case_endpoint(
    payload: ReviewCaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_CREATE")),
):
    """Create a manual review case initiated by an authorized officer or reviewer."""
    case = service.create_manual_review_case(
        db=db,
        payload=payload,
        user_id=current_user.id,
    )
    return ReviewCaseResponse.model_validate(case)


@router.get(
    "",
    response_model=ReviewCaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List review cases with filters and pagination",
)
def list_review_cases_endpoint(
    status_filter: Optional[ReviewStatus] = Query(None, alias="status"),
    priority_filter: Optional[ReviewPriority] = Query(None, alias="priority"),
    issue_type_filter: Optional[ReviewIssueType] = Query(None, alias="issue_type"),
    tender_id: Optional[uuid.UUID] = Query(None),
    tender_version_id: Optional[uuid.UUID] = Query(None),
    bidder_id: Optional[uuid.UUID] = Query(None),
    submission_id: Optional[uuid.UUID] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """List review cases matching optional criteria filters."""
    total, items = service.list_review_cases(
        db=db,
        status_filter=status_filter,
        priority_filter=priority_filter,
        issue_type_filter=issue_type_filter,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        bidder_id=bidder_id,
        submission_id=submission_id,
        assigned_to=assigned_to,
        skip=skip,
        limit=limit,
    )
    return ReviewCaseListResponse(
        total=total,
        items=[ReviewCaseResponse.model_validate(c) for c in items],
    )


@router.get(
    "/{review_id}",
    response_model=ReviewCaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complete review case detail with bounding boxes and OPA output",
)
def get_review_case_detail_endpoint(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Retrieve full review case details, evidence bounding boxes, OPA output, and decision history."""
    return service.get_review_case_detail(
        db=db,
        review_id=review_id,
    )


@router.post(
    "/{review_id}/assign",
    response_model=ReviewCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign review case to an officer",
)
def assign_review_case_endpoint(
    review_id: uuid.UUID,
    payload: ReviewAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_APPROVE")),
):
    """Assign a review case to an authorized procurement officer."""
    case = service.assign_review_case(
        db=db,
        review_id=review_id,
        assignee_id=payload.assigned_to,
        actor_id=current_user.id,
    )
    return ReviewCaseResponse.model_validate(case)


@router.post(
    "/{review_id}/decide",
    response_model=OfficerDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an explicit human decision (CONFIRM, OVERRIDE, REQUEST_REVIEW)",
)
def record_officer_decision_endpoint(
    review_id: uuid.UUID,
    payload: OfficerDecisionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_APPROVE")),
):
    """
    Record an explicit human officer review decision.
    Overrides strictly require a justification reason and final verdict.
    """
    decision = service.record_officer_decision(
        db=db,
        review_id=review_id,
        decision=payload.decision,
        reason=payload.reason,
        final_verdict=payload.final_verdict,
        officer_id=current_user.id,
    )
    return OfficerDecisionResponse.model_validate(decision)


@router.post(
    "/{review_id}/notes",
    response_model=ReviewNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an immutable review note",
)
def add_review_note_endpoint(
    review_id: uuid.UUID,
    payload: ReviewNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_CREATE")),
):
    """Add a structured, immutable review note."""
    note = service.add_review_note(
        db=db,
        review_id=review_id,
        note_text=payload.note,
        author_id=current_user.id,
    )
    return ReviewNoteResponse.model_validate(note)


@router.post(
    "/{review_id}/resolve",
    response_model=ReviewCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a review case",
)
def resolve_review_case_endpoint(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_APPROVE")),
):
    """Resolve a review case. Requires at least one recorded officer decision."""
    case = service.resolve_review_case(
        db=db,
        review_id=review_id,
        officer_id=current_user.id,
    )
    return ReviewCaseResponse.model_validate(case)


@router.post(
    "/{review_id}/reopen",
    response_model=ReviewCaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Reopen a resolved review case",
)
def reopen_review_case_endpoint(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REVIEW_APPROVE")),
):
    """Reopen a previously resolved review case."""
    case = service.reopen_review_case(
        db=db,
        review_id=review_id,
        officer_id=current_user.id,
    )
    return ReviewCaseResponse.model_validate(case)


@router.get(
    "/{review_id}/history",
    response_model=List[ReviewAuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get review case chronological audit trail",
)
def get_review_history_endpoint(
    review_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Retrieve the full chronological audit history for a review case."""
    logs = service.get_review_history(
        db=db,
        review_id=review_id,
    )
    return [ReviewAuditLogResponse.model_validate(l) for l in logs]
