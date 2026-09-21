"""Document service handling secure ingestion, metadata management, and storage synchronization."""

import io
import logging
import uuid
from typing import BinaryIO, List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.tender import Tender
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.documents.validators import (
    generate_storage_key,
    validate_and_process_upload_stream,
)
from app.storage.base import ObjectStorageService

logger = logging.getLogger("app.documents.service")


async def ingest_document(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    file: UploadFile,
    current_user: User,
    storage: ObjectStorageService,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> Document:
    """
    Ingest an uploaded procurement document:
    1. Verify parent tender and tender_version exist and are associated.
    2. Stream and validate file content (type, extension, signature, size, SHA-256).
    3. Upload binary file to object storage.
    4. Persist document metadata in PostgreSQL.
    5. Clean up orphaned storage object if PostgreSQL transaction fails.
    """
    settings = get_settings()

    # 1. Validate tender exists
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found.",
        )

    # 2. Validate tender_version exists and matches tender
    version = db.execute(
        select(TenderVersion).where(
            TenderVersion.id == tender_version_id,
            TenderVersion.tender_id == tender_id,
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TenderVersion '{tender_version_id}' not found for Tender '{tender_id}'.",
        )

    # 3. Stream and validate file
    file_bytes, safe_filename, ext, content_type, file_size, sha256_hash = (
        await validate_and_process_upload_stream(file, settings.MAX_UPLOAD_SIZE_MB)
    )

    document_id = uuid.uuid4()
    storage_key = generate_storage_key(tender_id, tender_version_id, document_id, safe_filename)

    # 4. Upload to Object Storage
    logger.info(
        "Uploading document binary to storage (tender_id=%s, version_id=%s, key=%s, size=%d)",
        tender_id,
        tender_version_id,
        storage_key,
        file_size,
    )
    try:
        storage.upload(
            key=storage_key,
            data=io.BytesIO(file_bytes),
            content_type=content_type,
        )
    except Exception as exc:
        logger.error("Object storage upload failed for key '%s': %s", storage_key, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store document binary in object storage.",
        )

    # 5. Persist Document Metadata in PostgreSQL with compensatory cleanup on error
    try:
        document = Document(
            id=document_id,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            filename=safe_filename,
            content_type=content_type,
            file_extension=ext,
            file_size=file_size,
            sha256_hash=sha256_hash,
            storage_key=storage_key,
            document_type=document_type,
            processing_status=ProcessingStatus.VALIDATED,
            uploaded_by=current_user.id,
        )
        db.add(document)
        db.flush()
        # Record audit event on document ingestion
        from app.audit.service import AuditService
        from app.audit.events import AuditAction
        user_role = current_user.roles[0].name if current_user.roles else "USER"
        AuditService.record(
            db,
            action=AuditAction.DOCUMENT_UPLOADED.value,
            entity_type="DOCUMENT",
            entity_id=str(document.id),
            actor_id=current_user.id,
            actor_role=user_role,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            document_id=document.id,
            document_hash=sha256_hash,
            reason="Procurement document uploaded and metadata persisted.",
            source_service="document_service",
            metadata_json={
                "filename": safe_filename,
                "file_size": file_size,
                "content_type": content_type,
                "storage_key": storage_key,
                "sha256_hash": sha256_hash,
            },
        )
        # Automatically enqueue processing job for background worker
        from app.pipeline.queue import enqueue_document_job
        job = enqueue_document_job(db=db, document_id=document.id)
        db.commit()
        db.refresh(document)
        setattr(document, "job_id", job.id)
        logger.info("Document metadata recorded and processing enqueued successfully (document_id=%s, job_id=%s)", document.id, job.id)
        return document
    except Exception as exc:
        db.rollback()
        logger.error(
            "Database metadata creation failed for document '%s'. Initiating orphan storage cleanup: %s",
            document_id,
            str(exc),
        )
        # Compensatory orphan cleanup
        try:
            storage.delete(storage_key)
            logger.info("Orphaned object successfully deleted from storage (key=%s)", storage_key)
        except Exception as cleanup_exc:
            logger.critical(
                "CRITICAL: Failed to clean up orphaned storage object (key=%s): %s",
                storage_key,
                str(cleanup_exc),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record document metadata.",
        )


def get_document_by_id(db: Session, document_id: uuid.UUID) -> Document:
    """Retrieve document metadata by document ID."""
    stmt = select(Document).where(Document.id == document_id)
    document = db.execute(stmt).scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return document


def get_document_file_stream(
    db: Session,
    document_id: uuid.UUID,
    storage: ObjectStorageService,
) -> Tuple[Document, BinaryIO]:
    """Retrieve document record and download binary stream from storage."""
    document = get_document_by_id(db, document_id)
    try:
        stream = storage.download(document.storage_key)
        return document, stream
    except FileNotFoundError:
        logger.error(
            "Document binary missing from storage for document '%s' (key=%s)",
            document_id,
            document.storage_key,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document binary file not found in storage.",
        )
    except Exception as exc:
        logger.error("Error retrieving document stream '%s': %s", document_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document binary.",
        )


def list_documents_for_version(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Document], int]:
    """List documents associated with a specific tender version."""
    base_query = select(Document).where(
        Document.tender_id == tender_id,
        Document.tender_version_id == tender_version_id,
    )
    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0
    items = (
        db.execute(base_query.order_by(Document.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(items), total
