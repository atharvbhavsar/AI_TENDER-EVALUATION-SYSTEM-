"""Audit API endpoints for querying system, entity audit records, and provenance."""

import datetime
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.audit.provenance import ProvenanceService
from app.audit.schemas import (
    AuditListResponse,
    AuditLogFilter,
    AuditLogResponse,
    CriterionProvenanceDetail,
    SubmissionProvenanceResponse,
)
from app.audit.service import AuditService
from app.auth.dependencies import (
    get_current_active_user,
    require_any_permission,
)
from app.db.models.bid_submission import BidSubmission
from app.db.models.document import Document
from app.db.models.tender import Tender
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get(
    "/logs",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="Query audit logs",
)
def get_audit_logs(
    tender_id: Optional[uuid.UUID] = Query(None, description="Filter by tender ID"),
    tender_version_id: Optional[uuid.UUID] = Query(None, description="Filter by tender version ID"),
    bidder_id: Optional[uuid.UUID] = Query(None, description="Filter by bidder ID"),
    bid_submission_id: Optional[uuid.UUID] = Query(None, description="Filter by bid submission ID"),
    criterion_id: Optional[uuid.UUID] = Query(None, description="Filter by criterion ID"),
    document_id: Optional[uuid.UUID] = Query(None, description="Filter by document ID"),
    evidence_id: Optional[uuid.UUID] = Query(None, description="Filter by evidence ID"),
    evaluation_id: Optional[uuid.UUID] = Query(None, description="Filter by evaluation ID"),
    review_id: Optional[uuid.UUID] = Query(None, description="Filter by review case ID"),
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor ID"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    start_time: Optional[datetime.datetime] = Query(None, description="Filter by minimum timestamp"),
    end_time: Optional[datetime.datetime] = Query(None, description="Filter by maximum timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ")),
) -> AuditListResponse:
    """Query immutable audit events with multi-field filtering and pagination."""
    filters = AuditLogFilter(
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        bidder_id=bidder_id,
        bid_submission_id=bid_submission_id,
        criterion_id=criterion_id,
        document_id=document_id,
        evidence_id=evidence_id,
        evaluation_id=evaluation_id,
        review_id=review_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    items, total = AuditService.query_logs(db, filters)
    return AuditListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/logs/{audit_id}",
    response_model=AuditLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single audit log by ID",
)
def get_audit_log_by_id(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ")),
) -> AuditLogResponse:
    """Retrieve an individual audit event by UUID."""
    entry = AuditService.get_by_id(db, audit_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AuditLog '{audit_id}' not found.",
        )
    return AuditLogResponse.model_validate(entry)


@router.get(
    "/tenders/{tender_id}",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get tender audit trail",
)
def get_tender_audit(
    tender_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ", "TENDER_READ")),
) -> AuditListResponse:
    """Retrieve the full chronological audit trail for a tender."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found.",
        )
    items, total = AuditService.get_tender_audit_trail(db, tender_id, limit=limit, offset=offset)
    return AuditListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get submission audit trail",
)
def get_submission_audit(
    submission_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AuditListResponse:
    """Retrieve the chronological audit trail for a bid submission with IDOR protection."""
    sub = db.query(BidSubmission).filter(BidSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BidSubmission '{submission_id}' not found.",
        )

    # Scoping check
    is_officer = current_user.has_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ", "EVALUATION_EXECUTE")
    if not is_officer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: insufficient permissions to view submission audit trail.",
        )

    items, total = AuditService.get_submission_audit_trail(db, submission_id, limit=limit, offset=offset)
    return AuditListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/documents/{document_id}",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document audit trail",
)
def get_document_audit(
    document_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "DOCUMENT_READ", "REPORT_READ")),
) -> AuditListResponse:
    """Retrieve the chronological audit trail for a specific document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    items, total = AuditService.get_document_audit_trail(db, document_id, limit=limit, offset=offset)
    return AuditListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/provenance/submissions/{submission_id}",
    response_model=SubmissionProvenanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconstruct full bid submission provenance and lineage",
)
def get_submission_provenance(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ")),
) -> SubmissionProvenanceResponse:
    """Reconstruct complete lineage: tender -> criteria -> documents -> evidence -> evaluation -> review decisions."""
    return ProvenanceService.reconstruct_submission_provenance(db, submission_id)


@router.get(
    "/provenance/criteria/{criterion_id}",
    response_model=CriterionProvenanceDetail,
    status_code=status.HTTP_200_OK,
    summary="Reconstruct criterion definition and rule provenance",
)
def get_criterion_provenance(
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("AUDIT_READ", "REPORT_READ", "EVALUATION_READ", "CRITERION_READ")),
) -> CriterionProvenanceDetail:
    """Reconstruct criterion rule, source location, and provenance."""
    return ProvenanceService.reconstruct_criterion_provenance(db, criterion_id)
