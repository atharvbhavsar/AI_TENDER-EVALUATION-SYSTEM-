"""Standalone and distributed background worker daemon processing document ingestion queue."""

import datetime
import logging
import os
import signal
import sys
import time
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.models.document import Document
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.db.session import SessionLocal
from app.pipeline.queue import fetch_next_job, mark_job_completed, mark_job_failed, recover_stalled_jobs
from app.pipeline.router import parse_document
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service
from app.workers.celery_app import celery_app

logger = logging.getLogger("app.workers.document_worker")


def process_single_job(
    db: Session,
    storage: ObjectStorageService,
    job: DocumentProcessingJob,
    worker_id: Optional[str] = None,
) -> bool:
    """
    Process a single document job from queue to completion or failure.
    
    Guarantees idempotency: exits safely without duplicate operations if already COMPLETED.
    """
    effective_worker_id = worker_id or f"worker-{os.getpid()}"

    # 1. IDEMPOTENCY CHECK
    if job.status == JobStatus.COMPLETED:
        logger.info("Job %s is already marked COMPLETED. Skipping duplicate execution.", job.id)
        return True

    doc = db.query(Document).filter(Document.id == job.document_id).first()
    if not doc:
        now = datetime.datetime.now(datetime.timezone.utc)
        job.failed_at = now
        job.worker_id = effective_worker_id
        mark_job_failed(
            db=db,
            job=job,
            error_code="DOCUMENT_NOT_FOUND",
            error_message=f"Document '{job.document_id}' not found in database.",
        )
        return False

    logger.info(
        "Worker %s processing document %s (filename=%s, type=%s, job=%s, attempt=%d)",
        effective_worker_id,
        doc.id,
        doc.filename,
        doc.file_extension,
        job.id,
        job.attempt_count,
    )

    doc_id = doc.id
    doc_filename = doc.filename
    doc_ext = doc.file_extension
    doc_storage_key = doc.storage_key
    doc_tender_id = doc.tender_id
    doc_version_id = doc.tender_version_id

    try:
        job.worker_id = effective_worker_id
        if not job.started_at:
            job.started_at = datetime.datetime.now(datetime.timezone.utc)

        # 1. Download original binary from object storage
        stream = storage.download(doc_storage_key)
        content_bytes = stream.read() if hasattr(stream, "read") else bytes(stream)

        # 2. Parse and normalize structured content
        normalized_doc = parse_document(
            document_id=doc_id,
            content=content_bytes,
            filename=doc_filename,
            file_extension=doc_ext,
        )

        # 3. Store normalized JSON artifact in Object Storage
        json_payload = normalized_doc.model_dump_json(indent=2).encode("utf-8")
        artifact_key = f"documents/tender/{doc_tender_id}/version/{doc_version_id}/{doc_id}/artifacts/normalized_content.json"

        storage.upload(
            key=artifact_key,
            data=json_payload,
            content_type="application/json",
        )

        # 4. Mark job completed and persist artifact metadata
        mark_job_completed(
            db=db,
            job=job,
            normalized_doc=normalized_doc,
            artifact_storage_key=artifact_key,
            artifact_size=len(json_payload),
        )
        return True

    except ValueError as val_err:
        logger.warning("Document parsing validation error for document %s: %s", doc_id, str(val_err))
        job.failed_at = datetime.datetime.now(datetime.timezone.utc)
        mark_job_failed(
            db=db,
            job=job,
            error_code="PARSER_VALIDATION_ERROR",
            error_message=str(val_err),
        )
        return False
    except Exception as exc:
        logger.error("Unexpected worker exception processing document %s: %s", doc_id, str(exc))
        job.failed_at = datetime.datetime.now(datetime.timezone.utc)
        mark_job_failed(
            db=db,
            job=job,
            error_code="UNEXPECTED_PROCESSING_FAILURE",
            error_message=str(exc),
        )
        return False


_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    logger.info("Received termination signal (%s). Initiating graceful worker shutdown...", signum)
    _shutdown_requested = True


def run_polling_worker(max_iterations: int | None = None) -> None:
    """Run database-polling worker loop (used as fallback or for embedded test runs)."""
    global _shutdown_requested
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("Starting Document Processing Polling Daemon v%s...", settings.PROCESSOR_VERSION)

    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except (ValueError, AttributeError):
        pass

    storage = get_storage_service()
    storage.ensure_bucket_exists()

    with SessionLocal() as db:
        recovered = recover_stalled_jobs(db)
        if recovered > 0:
            logger.info("Worker recovered %d stalled jobs on startup.", recovered)

    iterations = 0
    while not _shutdown_requested:
        if max_iterations is not None and iterations >= max_iterations:
            break
        iterations += 1

        with SessionLocal() as db:
            job = fetch_next_job(db)
            if job:
                process_single_job(db=db, storage=storage, job=job)
            else:
                time.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)

    logger.info("Document Processing Polling Daemon stopped gracefully.")


def start_celery_worker(concurrency: int | None = None) -> None:
    """Launch Celery distributed worker process pool with configured concurrency."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)

    # Recover any stalled jobs prior to starting consumers
    with SessionLocal() as db:
        recovered = recover_stalled_jobs(db)
        if recovered > 0:
            logger.info("Worker recovered %d stalled jobs on startup.", recovered)

    worker_concurrency = concurrency or settings.WORKER_CONCURRENCY
    pool_type = "threads" if sys.platform == "win32" else "prefork"

    argv = [
        "worker",
        f"--concurrency={worker_concurrency}",
        f"--pool={pool_type}",
        f"--loglevel={settings.LOG_LEVEL}",
        "-Q", "document_processing",
        "-n", f"doc_worker_{os.getpid()}@%h",
    ]
    logger.info("Launching Celery Worker: pool=%s, concurrency=%d", pool_type, worker_concurrency)
    celery_app.worker_main(argv)


def run_worker_loop(max_iterations: int | None = None) -> None:
    """Entrypoint preserving backward-compatible signature while supporting Celery or polling."""
    if "--poll" in sys.argv or max_iterations is not None:
        run_polling_worker(max_iterations=max_iterations)
    else:
        start_celery_worker()


if __name__ == "__main__":
    run_worker_loop()
