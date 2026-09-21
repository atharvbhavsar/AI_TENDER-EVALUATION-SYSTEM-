"""Asynchronous worker tasks for document processing and AI pipeline orchestration."""

import datetime
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import AuditAction
from app.audit.service import AuditService
from app.core.config import get_settings
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus, JobType
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.session import SessionLocal
from app.pipeline.router import parse_document
from app.storage.service import get_storage_service
from app.workers.celery_app import celery_app

logger = logging.getLogger("app.workers.tasks")

# Non-retryable error classifications: invalid structure, corrupt files, limit violations
NON_RETRYABLE_EXCEPTIONS = (
    ValueError,
    TypeError,
    json.JSONDecodeError,
)


def _is_retryable_error(exc: Exception) -> bool:
    """Determine whether an execution failure is transient or permanent."""
    msg = str(exc).lower()
    if isinstance(exc, NON_RETRYABLE_EXCEPTIONS):
        return False
    if "corrupted" in msg or "invalid" in msg or "exceeds maximum" in msg or "unsupported" in msg:
        return False
    return True


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document_job",
    max_retries=3,
    acks_late=True,
)
def process_document_job(self, job_id_str: str) -> Dict[str, Any]:
    """
    Execute document processing task asynchronously across distributed workers.
    
    Adheres to strict idempotency, safe transactional state transitions,
    controlled retries with exponential backoff, and full auditability.
    """
    settings = get_settings()
    job_uuid = uuid.UUID(job_id_str)
    worker_id = getattr(self.request, "hostname", None) or f"worker-{os.getpid()}"

    logger.info(
        "Worker %s received document job %s (attempt=%d)",
        worker_id,
        job_uuid,
        self.request.retries + 1,
    )

    storage = get_storage_service()

    with SessionLocal() as db:
        job = db.execute(
            select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_uuid)
        ).scalar_one_or_none()

        if not job:
            logger.error("Job %s not found in database. Exiting task.", job_uuid)
            return {"job_id": job_id_str, "status": "NOT_FOUND"}

        # 1. IDEMPOTENCY CHECK: If already COMPLETED, exit safely without duplicate processing
        if job.status == JobStatus.COMPLETED:
            logger.info("Job %s is already COMPLETED. Acknowledging safely (idempotent).", job.id)
            return {"job_id": job_id_str, "status": "COMPLETED", "idempotent": True}

        doc = db.execute(
            select(Document).where(Document.id == job.document_id)
        ).scalar_one_or_none()

        if not doc:
            now = datetime.datetime.now(datetime.timezone.utc)
            job.status = JobStatus.FAILED
            job.failed_at = now
            job.completed_at = now
            job.error_code = "DOCUMENT_NOT_FOUND"
            job.error_message = f"Document '{job.document_id}' not found."
            job.worker_id = worker_id
            db.commit()
            return {"job_id": job_id_str, "status": "FAILED", "error": "DOCUMENT_NOT_FOUND"}

        # 2. ATOMIC STATE TRANSITION: QUEUED -> PROCESSING
        now = datetime.datetime.now(datetime.timezone.utc)
        job.status = JobStatus.PROCESSING
        job.attempt_count += 1
        job.started_at = now
        job.worker_id = worker_id
        doc.processing_status = ProcessingStatus.PROCESSING
        db.commit()
        db.refresh(job)

        logger.info(
            "Worker %s started processing document %s (filename=%s, job=%s, attempt=%d)",
            worker_id,
            doc.id,
            doc.filename,
            job.id,
            job.attempt_count,
        )

        try:
            # 3. Retrieve original binary from Object Storage
            stream = storage.download(doc.storage_key)
            content_bytes = stream.read() if hasattr(stream, "read") else bytes(stream)

            # 4. Execute existing document-processing pipeline (PyMuPDF / Docling / PaddleOCR)
            normalized_doc = parse_document(
                document_id=doc.id,
                content=content_bytes,
                filename=doc.filename,
                file_extension=doc.file_extension,
            )

            # 5. Persist normalized JSON artifact in Object Storage
            json_payload = normalized_doc.model_dump_json(indent=2).encode("utf-8")
            artifact_key = f"documents/tender/{doc.tender_id}/version/{doc.tender_version_id}/{doc.id}/artifacts/normalized_content.json"
            storage.upload(
                key=artifact_key,
                data=json_payload,
                content_type="application/json",
            )

            # 6. Persist ProcessingArtifact metadata
            artifact = ProcessingArtifact(
                id=uuid.uuid4(),
                document_id=doc.id,
                artifact_type=ArtifactType.NORMALIZED_CONTENT,
                storage_key=artifact_key,
                file_size=len(json_payload),
                mime_type="application/json",
            )
            db.add(artifact)

            # 7. Update Job and Document state -> COMPLETED
            completed_time = datetime.datetime.now(datetime.timezone.utc)
            job.status = JobStatus.COMPLETED
            job.completed_at = completed_time
            job.error_code = None
            job.error_message = None
            doc.processing_status = ProcessingStatus.COMPLETED

            # Map detected document type if applicable
            detected_type = normalized_doc.document_type
            if hasattr(DocumentType, detected_type):
                doc.document_type = DocumentType[detected_type]

            # 8. Emit structured audit log
            AuditService.record(
                db=db,
                action=AuditAction.DOCUMENT_PROCESSED.value if hasattr(AuditAction, "DOCUMENT_PROCESSED") else "DOCUMENT_PROCESSED",
                entity_type="DOCUMENT",
                entity_id=str(doc.id),
                actor_id=doc.uploaded_by,
                actor_role="SYSTEM_WORKER",
                tender_id=doc.tender_id,
                tender_version_id=doc.tender_version_id,
                document_id=doc.id,
                reason=f"Document processed successfully by worker {worker_id}.",
                source_service="document_worker",
                metadata_json={
                    "job_id": str(job.id),
                    "worker_id": worker_id,
                    "pages": normalized_doc.page_count,
                    "characters": normalized_doc.total_characters,
                    "tables": normalized_doc.total_tables,
                    "artifact_key": artifact_key,
                },
            )

            db.commit()
            logger.info(
                "Successfully completed processing job %s for document %s by %s (pages=%d, chars=%d)",
                job.id,
                doc.id,
                worker_id,
                normalized_doc.page_count,
                normalized_doc.total_characters,
            )
            return {
                "job_id": str(job.id),
                "document_id": str(doc.id),
                "status": "COMPLETED",
                "worker_id": worker_id,
                "pages": normalized_doc.page_count,
            }

        except Exception as exc:
            db.rollback()
            is_retryable = _is_retryable_error(exc)
            logger.warning(
                "Processing error on job %s (retryable=%s): %s",
                job.id,
                is_retryable,
                str(exc),
            )

            now = datetime.datetime.now(datetime.timezone.utc)
            # Safe sanitized error message
            err_msg = str(exc)[:500] if str(exc) else "Unknown processing failure"

            # Check if retryable and retry budget remains
            if is_retryable and job.attempt_count < job.max_attempts:
                job.status = JobStatus.RETRYING
                job.error_code = "TRANSIENT_PROCESSING_ERROR"
                job.error_message = err_msg
                db.commit()

                # Exponential backoff: 2s, 4s, 8s...
                backoff = min(60, 2 ** (job.attempt_count - 1))
                logger.warning(
                    "Re-scheduling job %s for retry in %ds (attempt %d/%d)",
                    job.id,
                    backoff,
                    job.attempt_count,
                    job.max_attempts,
                )
                raise self.retry(exc=exc, countdown=backoff)
            else:
                # Permanent failure: no more retries
                job.status = JobStatus.FAILED
                job.failed_at = now
                job.completed_at = now
                job.error_code = "PARSER_VALIDATION_ERROR" if isinstance(exc, ValueError) else "PROCESSING_FAILED"
                job.error_message = err_msg
                doc.processing_status = ProcessingStatus.FAILED

                AuditService.record(
                    db=db,
                    action="DOCUMENT_PROCESSING_FAILED",
                    entity_type="DOCUMENT",
                    entity_id=str(doc.id),
                    actor_id=doc.uploaded_by,
                    actor_role="SYSTEM_WORKER",
                    tender_id=doc.tender_id,
                    tender_version_id=doc.tender_version_id,
                    document_id=doc.id,
                    reason=f"Document processing failed permanently: {err_msg}",
                    source_service="document_worker",
                    metadata_json={
                        "job_id": str(job.id),
                        "worker_id": worker_id,
                        "error_code": job.error_code,
                        "attempts": job.attempt_count,
                    },
                )
                db.commit()
                logger.error(
                    "Job %s failed permanently after %d attempts: %s",
                    job.id,
                    job.attempt_count,
                    err_msg,
                )
                return {
                    "job_id": str(job.id),
                    "document_id": str(doc.id),
                    "status": "FAILED",
                    "error": err_msg,
                }
