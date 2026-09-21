"""REST API endpoints for Bidders, Submissions, and Evidence Extraction."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.document import DocumentType
from app.db.models.evidence import EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.user import User
from app.db.session import get_db
from app.documents import service as doc_service
from app.documents.schemas import DocumentResponse
from app.evidence import service
from app.evidence.schemas import (
    BidderCreate,
    BidderListResponse,
    BidderResponse,
    BidSubmissionCreate,
    BidSubmissionListResponse,
    BidSubmissionResponse,
    EvidenceExtractionRunResponse,
    EvidenceExtractionTriggerRequest,
    EvidenceListResponse,
    EvidenceResponse,
)
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

router = APIRouter(tags=["Evidence & Bidder Submissions"])


# --- Bidder Endpoints ---

@router.post(
    "/tenders/{tender_id}/bidders",
    response_model=BidderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new bidder under a tender",
)
def create_bidder(
    tender_id: uuid.UUID,
    data: BidderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
) -> BidderResponse:
    """Register a new legal bidder entity for participation in the specified tender."""
    bidder = service.create_bidder(db=db, tender_id=tender_id, data=data)
    return BidderResponse.model_validate(bidder)


@router.get(
    "/tenders/{tender_id}/bidders",
    response_model=BidderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all bidders registered for a tender",
)
def list_bidders(
    tender_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> BidderListResponse:
    """List bidders registered for the tender."""
    items, total = service.list_bidders(db=db, tender_id=tender_id, skip=skip, limit=limit)
    return BidderListResponse(
        items=[BidderResponse.model_validate(b) for b in items],
        total=total,
    )


# --- Bid Submission Endpoints ---

@router.post(
    "/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions",
    response_model=BidSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bid submission against a specific tender version",
)
def create_submission(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    data: BidSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
) -> BidSubmissionResponse:
    """Create a new bid submission package for a bidder scoped strictly to a tender version."""
    submission = service.create_submission(
        db=db,
        tender_id=tender_id,
        version_id=version_id,
        bidder_id=bidder_id,
        data=data,
    )
    resp = BidSubmissionResponse.model_validate(submission)
    resp.document_count = len(submission.documents)
    return resp


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions",
    response_model=BidSubmissionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List submissions for a bidder under a specific tender version",
)
def list_submissions(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> BidSubmissionListResponse:
    """Retrieve all submissions for a bidder under a tender version."""
    items, total = service.list_submissions(
        db=db,
        tender_id=tender_id,
        version_id=version_id,
        bidder_id=bidder_id,
        skip=skip,
        limit=limit,
    )
    result_items = []
    for s in items:
        res = BidSubmissionResponse.model_validate(s)
        res.document_count = len(s.documents)
        result_items.append(res)

    return BidSubmissionListResponse(items=result_items, total=total)


# --- Submission Document Ingestion ---

@router.post(
    "/submissions/{submission_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document for a bidder submission",
)
async def upload_submission_document(
    submission_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_UPLOAD")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> DocumentResponse:
    """Ingest a secure document (PDF, Word, Spreadsheet, Image) for a bidder submission."""
    submission = service.get_submission(db=db, submission_id=submission_id)

    # Ingest document through Phase 5 document service
    document = await doc_service.ingest_document(
        db=db,
        tender_id=submission.tender_version.tender_id,
        tender_version_id=submission.tender_version_id,
        file=file,
        current_user=current_user,
        storage=storage,
        document_type=document_type,
    )
    # Associate document with this submission
    document.bid_submission_id = submission_id
    db.commit()
    db.refresh(document)

    return DocumentResponse.model_validate(document)


# --- Evidence Extraction Trigger & Status ---

@router.post(
    "/submissions/{submission_id}/evidence/extract",
    response_model=EvidenceExtractionRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI evidence extraction against approved criteria",
)
async def trigger_evidence_extraction(
    submission_id: uuid.UUID,
    payload: Optional[EvidenceExtractionTriggerRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> EvidenceExtractionRunResponse:
    """
    Trigger evidence extraction for a submission against officer-approved criteria.
    Validates that only APPROVED criteria are extracted against.
    """
    crit_id = payload.criterion_id if payload else None
    run = await service.extract_submission_evidence(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
        criterion_id=crit_id,
        storage=storage,
    )
    return EvidenceExtractionRunResponse.model_validate(run)


@router.get(
    "/submissions/{submission_id}/evidence/extraction-status",
    response_model=list[EvidenceExtractionRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Get status of evidence extraction runs for a submission",
)
def get_evidence_extraction_status(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> list[EvidenceExtractionRunResponse]:
    """Retrieve extraction run history for a bidder submission."""
    service.get_submission(db=db, submission_id=submission_id)
    runs = db.execute(
        select(EvidenceExtractionRun)
        .where(EvidenceExtractionRun.bid_submission_id == submission_id)
        .order_by(EvidenceExtractionRun.created_at.desc())
    ).scalars().all()
    return [EvidenceExtractionRunResponse.model_validate(r) for r in runs]


# --- Evidence Listing & Retrieval ---

@router.get(
    "/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions/{submission_id}/evidence",
    response_model=EvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted evidence for a bidder submission with filters",
)
def list_submission_evidence(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    submission_id: uuid.UUID,
    criterion_id: Optional[uuid.UUID] = Query(None),
    evidence_status: Optional[EvidenceStatus] = Query(None),
    document_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> EvidenceListResponse:
    """Retrieve evidence items for a submission filtered by criterion or evidence status."""
    # Validate relationship hierarchy
    submission = service.get_submission(db=db, submission_id=submission_id)
    if (
        submission.tender_version_id != version_id
        or submission.bidder_id != bidder_id
        or submission.tender_version.tender_id != tender_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission does not match the specified tender, version, or bidder.",
        )

    items, total = service.list_submission_evidence(
        db=db,
        submission_id=submission_id,
        criterion_id=criterion_id,
        evidence_status=evidence_status,
        document_id=document_id,
        skip=skip,
        limit=limit,
    )

    response_items = []
    for ev in items:
        item_dto = EvidenceResponse.model_validate(ev)
        if ev.criterion:
            item_dto.criterion_code = ev.criterion.criterion_code
            item_dto.criterion_name = ev.criterion.name
        if ev.document:
            item_dto.document_name = ev.document.filename
        response_items.append(item_dto)

    return EvidenceListResponse(items=response_items, total=total)


@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve single evidence item with source traceability",
)
def get_evidence_detail(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> EvidenceResponse:
    """Retrieve full details of an extracted evidence record including document, block, and bounding box."""
    evidence = service.get_evidence_by_id(db=db, evidence_id=evidence_id)
    item_dto = EvidenceResponse.model_validate(evidence)
    if evidence.criterion:
        item_dto.criterion_code = evidence.criterion.criterion_code
        item_dto.criterion_name = evidence.criterion.name
    if evidence.document:
        item_dto.document_name = evidence.document.filename
    return item_dto
