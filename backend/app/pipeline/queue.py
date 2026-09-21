"""Persistent job queue management for asynchronous document processing."""

import datetime
import logging
import uuid
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.pipeline.schemas import NormalizedDocument

logger = logging.getLogger("app.pipeline.queue")


def enqueue_document_job(
    db: Session,
    document_id: uuid.UUID,
    job_type: str = "DOCUMENT_PROCESSING",
    priority: int = 0,
    publish_redis: bool = True,
) -> DocumentProcessingJob:
    """
    Enqueue a new document processing job.
    
    Adheres strictly to the Transaction Rule: commits PostgreSQL state first,
    then dispatches the task to the Redis queue.
    """
    settings = get_settings()

    document = db.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if not document:
        raise ValueError(f"Document '{document_id}' not found.")

    # Check if there is already an active job
    existing_job = db.execute(
        select(DocumentProcessingJob).where(
            DocumentProcessingJob.document_id == document_id,
            DocumentProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.RETRYING]),
        )
    ).scalar_one_or_none()

    if existing_job:
        logger.info("Active processing job %s already exists for document %s", existing_job.id, document_id)
        return existing_job

    job = DocumentProcessingJob(
        id=uuid.uuid4(),
        document_id=document_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        priority=priority,
        attempt_count=0,
        max_attempts=settings.MAX_JOB_ATTEMPTS,
        processor_version=settings.PROCESSOR_VERSION,
    )
    db.add(job)
    # 1. COMMIT DATABASE TRANSACTION FIRST
    db.commit()
    db.refresh(job)
    logger.info("Enqueued processing job %s for document %s (type=%s)", job.id, document_id, job_type)

    # 2. DISPATCH TO REDIS QUEUE AFTER COMMIT
    if publish_redis:
        try:
            import redis
            _r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.1, socket_timeout=0.1)
            _r.ping()
            from app.workers.tasks import process_document_job
            process_document_job.apply_async(
                args=[str(job.id)],
                queue="document_processing",
                priority=priority,
                retry=False,
            )
            logger.info("Published job %s to Redis queue 'document_processing'", job.id)
        except Exception as redis_exc:
            logger.warning(
                "Redis publication skipped or failed for job %s (DB state safely preserved as QUEUED): %s",
                job.id,
                redis_exc,
            )

    return job


def fetch_next_job(db: Session) -> Optional[DocumentProcessingJob]:
    """Fetch next available queued job using row locking."""
    # SQLite doesn't support SKIP LOCKED, Postgres does
    bind = db.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    stmt = select(DocumentProcessingJob).where(
        DocumentProcessingJob.status == JobStatus.QUEUED
    ).order_by(DocumentProcessingJob.created_at.asc())

    if not is_sqlite:
        stmt = stmt.with_for_update(skip_locked=True)

    job = db.execute(stmt).scalars().first()
    if not job:
        return None

    job.status = JobStatus.PROCESSING
    job.attempt_count += 1
    job.started_at = datetime.datetime.now(datetime.timezone.utc)
    
    doc = db.execute(select(Document).where(Document.id == job.document_id)).scalar_one_or_none()
    if doc:
        doc.processing_status = ProcessingStatus.PROCESSING

    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(
    db: Session,
    job: DocumentProcessingJob,
    normalized_doc: NormalizedDocument,
    artifact_storage_key: str,
    artifact_size: int,
) -> None:
    """Mark job completed, persist artifact metadata, and update document status."""
    now = datetime.datetime.now(datetime.timezone.utc)
    job.status = JobStatus.COMPLETED
    job.completed_at = now
    job.error_code = None
    job.error_message = None

    # Persist artifact record
    artifact = ProcessingArtifact(
        id=uuid.uuid4(),
        document_id=job.document_id,
        artifact_type=ArtifactType.NORMALIZED_CONTENT,
        storage_key=artifact_storage_key,
        file_size=artifact_size,
        mime_type="application/json",
    )
    db.add(artifact)

    # Update document status and type
    doc = db.execute(select(Document).where(Document.id == job.document_id)).scalar_one_or_none()
    if doc:
        doc.processing_status = ProcessingStatus.COMPLETED
        # Map detected document type if known
        detected_type = normalized_doc.document_type
        if hasattr(DocumentType, detected_type):
            doc.document_type = DocumentType[detected_type]

    db.commit()
    logger.info("Successfully completed processing job %s for document %s", job.id, job.document_id)


NON_RETRYABLE_ERROR_CODES = {
    "PARSER_VALIDATION_ERROR",
    "CORRUPT_DOCUMENT",
    "INVALID_STRUCTURE",
    "UNSUPPORTED_TYPE",
    "LIMIT_EXCEEDED",
    "DOCUMENT_NOT_FOUND",
    "UNSUPPORTED_FILE_TYPE",
}


def mark_job_failed(
    db: Session,
    job: DocumentProcessingJob,
    error_code: str,
    error_message: str,
    retryable: bool = True,
) -> None:
    """Record job failure and manage retry eligibility according to error classification."""
    now = datetime.datetime.now(datetime.timezone.utc)
    clean_error = error_message[:500] if error_message else "Unknown error"
    job.error_code = error_code
    job.error_message = clean_error

    is_retryable = retryable and (error_code not in NON_RETRYABLE_ERROR_CODES)

    if is_retryable and job.attempt_count < job.max_attempts:
        job.status = JobStatus.QUEUED
        logger.warning(
            "Job %s failed (attempt %d/%d): %s. Re-queued for retry.",
            job.id,
            job.attempt_count,
            job.max_attempts,
            clean_error,
        )
    else:
        job.status = JobStatus.FAILED
        job.failed_at = now
        job.completed_at = now
        logger.error(
            "Job %s permanently failed (retryable=%s, attempts=%d): %s",
            job.id,
            is_retryable,
            job.attempt_count,
            clean_error,
        )
        doc = db.execute(select(Document).where(Document.id == job.document_id)).scalar_one_or_none()
        if doc:
            doc.processing_status = ProcessingStatus.FAILED

    db.commit()


def recover_stalled_jobs(db: Session, timeout_seconds: Optional[int] = None) -> int:
    """
    Find jobs stuck in PROCESSING state due to worker crashes or ungraceful terminations
    and safely reset or fail them.
    """
    settings = get_settings()
    timeout = timeout_seconds or settings.PROCESSING_TIMEOUT_SECONDS
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=timeout)

    stalled_jobs = db.execute(
        select(DocumentProcessingJob).where(
            DocumentProcessingJob.status == JobStatus.PROCESSING,
            DocumentProcessingJob.started_at < cutoff,
        )
    ).scalars().all()

    recovered_count = 0
    for job in stalled_jobs:
        logger.warning("Recovering stalled job %s (started_at=%s)", job.id, job.started_at)
        mark_job_failed(
            db=db,
            job=job,
            error_code="WORKER_TIMEOUT_OR_CRASH",
            error_message=f"Job processing stalled for >{timeout}s, likely due to worker crash.",
        )
        recovered_count += 1

    return recovered_count
