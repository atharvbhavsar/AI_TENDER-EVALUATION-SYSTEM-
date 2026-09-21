"""Document cryptographic SHA-256 integrity verification service for Phase 16."""

import datetime
import hashlib
import logging
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import AuditAction
from app.audit.schemas import DocumentIntegrityResponse, IntegrityStatus
from app.audit.service import AuditService
from app.db.models.document import Document
from app.db.models.user import User
from app.storage.base import ObjectStorageService

logger = logging.getLogger("app.documents.integrity")


def compute_sha256_from_stream(stream) -> str:
    """Compute SHA-256 hexadecimal digest from a readable binary stream."""
    hasher = hashlib.sha256()
    if hasattr(stream, "read"):
        while chunk := stream.read(64 * 1024):
            hasher.update(chunk)
    elif hasattr(stream, "__iter__"):
        for chunk in stream:
            hasher.update(chunk)
    else:
        raise ValueError("Unsupported stream object for hashing.")
    return hasher.hexdigest().lower()


def verify_document_integrity(
    db: Session,
    document_id: uuid.UUID,
    storage: ObjectStorageService,
    current_user: Optional[User] = None,
    correlation_id: Optional[str] = None,
) -> DocumentIntegrityResponse:
    """
    Cryptographically verify the integrity of a stored document:
    1. Retrieve original document metadata and stored sha256_hash.
    2. Download raw binary stream from object storage.
    3. Compute SHA-256 digest of downloaded binary.
    4. Compare computed hash with stored hash.
    5. Emit structured audit event (DOCUMENT_INTEGRITY_CHECKED or DOCUMENT_INTEGRITY_MISMATCH).
    6. Return structured DocumentIntegrityResponse without modifying original hash.
    """
    stmt = select(Document).where(Document.id == document_id)
    doc = db.execute(stmt).scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    actor_id = current_user.id if current_user else None
    actor_role = current_user.roles[0].name if current_user and current_user.roles else "SYSTEM"

    # Attempt to download binary from object storage
    try:
        stream = storage.download(doc.storage_key)
        computed_hash = compute_sha256_from_stream(stream)
    except FileNotFoundError:
        logger.error(
            "Document binary missing from storage during integrity check: doc_id=%s key=%s",
            doc.id,
            doc.storage_key,
        )
        AuditService.record(
            db,
            action=AuditAction.DOCUMENT_INTEGRITY_CHECKED.value,
            entity_type="DOCUMENT",
            entity_id=str(doc.id),
            actor_id=actor_id,
            actor_role=actor_role,
            tender_id=doc.tender_id,
            tender_version_id=doc.tender_version_id,
            document_id=doc.id,
            document_hash=doc.sha256_hash,
            reason="Document binary file missing from storage.",
            correlation_id=correlation_id,
            source_service="integrity_verifier",
            metadata_json={
                "integrity_status": IntegrityStatus.UNAVAILABLE.value,
                "storage_key": doc.storage_key,
                "error": "FileNotFoundError",
            },
        )
        return DocumentIntegrityResponse(
            document_id=doc.id,
            filename=doc.filename,
            stored_sha256=doc.sha256_hash,
            computed_sha256=None,
            integrity_status=IntegrityStatus.UNAVAILABLE,
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            message="Document binary is unavailable in object storage.",
        )
    except Exception as exc:
        logger.error(
            "Object storage error during integrity check for doc_id=%s: %s",
            doc.id,
            str(exc),
        )
        AuditService.record(
            db,
            action=AuditAction.DOCUMENT_INTEGRITY_CHECKED.value,
            entity_type="DOCUMENT",
            entity_id=str(doc.id),
            actor_id=actor_id,
            actor_role=actor_role,
            tender_id=doc.tender_id,
            tender_version_id=doc.tender_version_id,
            document_id=doc.id,
            document_hash=doc.sha256_hash,
            reason=f"Object storage access failed: {str(exc)}",
            correlation_id=correlation_id,
            source_service="integrity_verifier",
            metadata_json={
                "integrity_status": IntegrityStatus.UNAVAILABLE.value,
                "storage_key": doc.storage_key,
                "error": str(exc),
            },
        )
        return DocumentIntegrityResponse(
            document_id=doc.id,
            filename=doc.filename,
            stored_sha256=doc.sha256_hash,
            computed_sha256=None,
            integrity_status=IntegrityStatus.UNAVAILABLE,
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            message="Failed to access document binary in storage.",
        )

    # Compare SHA-256 hashes
    stored_hash_normalized = doc.sha256_hash.strip().lower()
    if computed_hash == stored_hash_normalized:
        integrity_status = IntegrityStatus.VERIFIED
        action = AuditAction.DOCUMENT_INTEGRITY_CHECKED.value
        reason = "Cryptographic SHA-256 hash verified successfully."
        message = "Document integrity verified: binary matches stored SHA-256."
    else:
        integrity_status = IntegrityStatus.MISMATCH
        action = AuditAction.DOCUMENT_INTEGRITY_MISMATCH.value
        reason = "CRITICAL: SHA-256 hash mismatch detected between stored metadata and object storage binary."
        message = f"Integrity mismatch detected: stored={stored_hash_normalized}, computed={computed_hash}"
        logger.critical(
            "INTEGRITY MISMATCH DETECTED for document %s: stored=%s, computed=%s",
            doc.id,
            stored_hash_normalized,
            computed_hash,
        )

    # Record audit event
    AuditService.record(
        db,
        action=action,
        entity_type="DOCUMENT",
        entity_id=str(doc.id),
        actor_id=actor_id,
        actor_role=actor_role,
        tender_id=doc.tender_id,
        tender_version_id=doc.tender_version_id,
        document_id=doc.id,
        document_hash=doc.sha256_hash,
        reason=reason,
        correlation_id=correlation_id,
        source_service="integrity_verifier",
        metadata_json={
            "integrity_status": integrity_status.value,
            "stored_sha256": stored_hash_normalized,
            "computed_sha256": computed_hash,
            "storage_key": doc.storage_key,
        },
    )

    return DocumentIntegrityResponse(
        document_id=doc.id,
        filename=doc.filename,
        stored_sha256=stored_hash_normalized,
        computed_sha256=computed_hash,
        integrity_status=integrity_status,
        verified_at=datetime.datetime.now(datetime.timezone.utc),
        message=message,
    )
