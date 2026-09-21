"""API endpoints for document processing status, content extraction, and execution triggering."""

import json
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permissions
from app.db.models.document import Document, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.user import User
from app.db.session import get_db
from app.pipeline.queue import enqueue_document_job
from app.pipeline.schemas import (
    DocumentBatchItemStatus,
    DocumentBatchStatusResponse,
    DocumentProcessingStatusResponse,
    NormalizedDocument,
    ProcessDocumentResponse,
)
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

logger = logging.getLogger("app.pipeline.api")
router = APIRouter(tags=["Document Processing"])


@router.get(
    "/documents/{document_id}/processing-status",
    response_model=DocumentProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document processing status and history",
)
def get_processing_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentProcessingStatusResponse:
    """Retrieve current processing status, active job state, and error code if failed."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # Get latest job if any
    job = (
        db.execute(
            select(DocumentProcessingJob)
            .where(DocumentProcessingJob.document_id == document_id)
            .order_by(DocumentProcessingJob.created_at.desc())
        )
        .scalars()
        .first()
    )

    return DocumentProcessingStatusResponse(
        document_id=doc.id,
        job_id=job.id if job else None,
        status=doc.processing_status.value,
        processor_version=job.processor_version if job else "1.0.0",
        attempt_count=job.attempt_count if job else 0,
        max_attempts=job.max_attempts if job else 3,
        started_at=job.started_at.isoformat() if job and job.started_at else None,
        completed_at=job.completed_at.isoformat() if job and job.completed_at else None,
        error_code=job.error_code if job else None,
        worker_id=job.worker_id if job else None,
    )


@router.get(
    "/documents/{document_id}/content",
    response_model=NormalizedDocument,
    status_code=status.HTTP_200_OK,
    summary="Retrieve structured normalized document content and blocks",
)
def get_normalized_content(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> NormalizedDocument:
    """Retrieve normalized extracted content, paragraphs, headings, and tables."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    if doc.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document '{document_id}' is not yet processed (current status: {doc.processing_status.value}).",
        )

    # Find normalized content artifact
    artifact = (
        db.execute(
            select(ProcessingArtifact).where(
                ProcessingArtifact.document_id == document_id,
                ProcessingArtifact.artifact_type == ArtifactType.NORMALIZED_CONTENT,
            )
        )
        .scalars()
        .first()
    )

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Normalized processing artifact not found in database.",
        )

    try:
        stream = storage.download(artifact.storage_key)
        data = stream.read() if hasattr(stream, "read") else bytes(stream)
        parsed_json = json.loads(data.decode("utf-8"))
        return NormalizedDocument.model_validate(parsed_json)
    except Exception as exc:
        logger.error("Failed to read normalized content artifact '%s': %s", artifact.storage_key, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load document content from storage.",
        )


@router.post(
    "/documents/{document_id}/process",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger or retry document processing",
)
def trigger_document_processing(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_UPLOAD")),
) -> ProcessDocumentResponse:
    """Trigger background document processing or re-try a failed job."""
    doc = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    job = enqueue_document_job(db=db, document_id=document_id)
    return ProcessDocumentResponse(
        message="Document processing job enqueued successfully.",
        job_id=job.id,
        document_id=doc.id,
        status=job.status.value,
    )


def _build_batch_status(
    documents: list[Document],
    db: Session,
    batch_type: str = "GENERIC",
    tender_id: Optional[uuid.UUID] = None,
    tender_version_id: Optional[uuid.UUID] = None,
    submission_id: Optional[uuid.UUID] = None,
) -> DocumentBatchStatusResponse:
    """Helper to compute aggregated batch status and item details."""
    total = len(documents)
    completed = 0
    processing = 0
    queued = 0
    failed = 0
    retrying = 0
    items: list[DocumentBatchItemStatus] = []

    for doc in documents:
        # Fetch latest job for this document
        job = (
            db.execute(
                select(DocumentProcessingJob)
                .where(DocumentProcessingJob.document_id == doc.id)
                .order_by(DocumentProcessingJob.created_at.desc())
            )
            .scalars()
            .first()
        )

        job_status = job.status.value if job else doc.processing_status.value
        if job_status == "COMPLETED" or doc.processing_status == ProcessingStatus.COMPLETED:
            completed += 1
            effective_status = "COMPLETED"
        elif job_status == "PROCESSING" or doc.processing_status == ProcessingStatus.PROCESSING:
            processing += 1
            effective_status = "PROCESSING"
        elif job_status == "RETRYING":
            retrying += 1
            effective_status = "RETRYING"
        elif job_status == "FAILED" or doc.processing_status == ProcessingStatus.FAILED:
            failed += 1
            effective_status = "FAILED"
        else:
            queued += 1
            effective_status = "QUEUED"

        items.append(
            DocumentBatchItemStatus(
                document_id=doc.id,
                job_id=job.id if job else None,
                filename=doc.filename,
                file_extension=doc.file_extension,
                document_type=doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
                status=effective_status,
                job_type=job.job_type if job else "DOCUMENT_PROCESSING",
                attempt_count=job.attempt_count if job else 0,
                max_attempts=job.max_attempts if job else 3,
                worker_id=job.worker_id if job else None,
                started_at=job.started_at.isoformat() if job and job.started_at else None,
                completed_at=job.completed_at.isoformat() if job and job.completed_at else None,
                failed_at=job.failed_at.isoformat() if job and job.failed_at else None,
                error_code=job.error_code if job else None,
            )
        )

    is_complete = total > 0 and (completed + failed == total)

    return DocumentBatchStatusResponse(
        total=total,
        completed=completed,
        processing=processing,
        queued=queued,
        failed=failed,
        retrying=retrying,
        is_complete=is_complete,
        batch_type=batch_type,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        submission_id=submission_id,
        items=items,
    )


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/processing-status",
    response_model=DocumentBatchStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated document processing status for a tender version batch",
)
def get_tender_batch_processing_status(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentBatchStatusResponse:
    """Retrieve completion and status for all documents belonging to a tender version."""
    docs = (
        db.execute(
            select(Document).where(
                Document.tender_id == tender_id,
                Document.tender_version_id == version_id,
            )
        )
        .scalars()
        .all()
    )

    return _build_batch_status(
        documents=docs,
        db=db,
        batch_type="TENDER_DOCUMENTS",
        tender_id=tender_id,
        tender_version_id=version_id,
    )


@router.get(
    "/submissions/{submission_id}/processing-status",
    response_model=DocumentBatchStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated document processing status for a bidder submission batch",
)
def get_submission_batch_processing_status(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentBatchStatusResponse:
    """Retrieve completion and status for all documents belonging to a bidder submission."""
    docs = (
        db.execute(
            select(Document).where(Document.bid_submission_id == submission_id)
        )
        .scalars()
        .all()
    )

    return _build_batch_status(
        documents=docs,
        db=db,
        batch_type="BIDDER_SUBMISSION_DOCUMENTS",
        submission_id=submission_id,
    )

