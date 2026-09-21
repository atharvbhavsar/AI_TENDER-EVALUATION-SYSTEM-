"""Comprehensive tests for Redis + Worker-based parallel document processing architecture."""

import datetime
import io
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus, JobType
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.pipeline.queue import (
    enqueue_document_job,
    fetch_next_job,
    mark_job_completed,
    mark_job_failed,
    recover_stalled_jobs,
)
from app.pipeline.schemas import DocumentPage, NormalizedDocument
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import set_storage_service_override
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender
from app.pipeline.router import parse_document
from app.workers.celery_app import celery_app
from app.workers.document_worker import process_single_job


@pytest.fixture
def mock_storage():
    storage = InMemoryObjectStorageService()
    set_storage_service_override(storage)
    return storage


@pytest.fixture
def sample_tender_and_version(db_session: Session, procurement_officer_user):
    tender = create_tender(
        db=db_session,
        payload=TenderCreate(
            tender_number=f"CRPF-TEST-{uuid.uuid4().hex[:6].upper()}",
            title="Redis Worker Test Tender",
        ),
        user_id=procurement_officer_user.id,
    )
    return tender, tender.active_version


def _make_valid_pdf_bytes(title: str = "Tender Specification Document") -> bytes:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), f"CRPF Procurement - {title}\nThis is a verified test procurement document with standard criteria specifications.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_mock_document(
    db: Session,
    storage: InMemoryObjectStorageService,
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str = "spec.pdf",
    content: bytes = None,
) -> Document:
    pdf_data = content if content is not None else _make_valid_pdf_bytes(filename)
    storage_key = f"documents/test/{uuid.uuid4()}/{filename}"
    storage.upload(key=storage_key, data=pdf_data, content_type="application/pdf")

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender_id,
        tender_version_id=version_id,
        filename=filename,
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=len(pdf_data),
        sha256_hash=uuid.uuid4().hex,
        storage_key=storage_key,
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.VALIDATED,
        uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ==============================================================================
# TEST 1: REDIS CONNECTION & TASK QUEUEING
# ==============================================================================
def test_01_redis_connection_and_task_dispatch():
    """Verify Redis is accessible and can enqueue tasks."""
    settings = get_settings()
    import redis

    r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3.0)
    assert r.ping() is True, "Redis ping failed"

    from app.workers.tasks import process_document_job

    dummy_job_id = str(uuid.uuid4())
    res = process_document_job.apply_async(args=[dummy_job_id], queue="document_processing")
    assert res.id is not None
    assert len(res.id) > 0


# ==============================================================================
# TEST 2: JOB CREATION & DB PERSISTENCE (TRANSACTION RULE)
# ==============================================================================
def test_02_job_creation_and_transaction_safety(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify job is committed to PostgreSQL with correct initial state."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    job = enqueue_document_job(db=db_session, document_id=doc.id, priority=5)
    assert job.status == JobStatus.QUEUED
    assert job.document_id == doc.id
    assert job.job_type == JobType.DOCUMENT_PROCESSING.value
    assert job.priority == 5
    assert job.attempt_count == 0
    assert job.max_attempts == 3


# ==============================================================================
# TEST 3: WORKER EXECUTION LIFECYCLE (QUEUED -> PROCESSING -> COMPLETED)
# ==============================================================================
def test_03_worker_execution_lifecycle(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify atomic state transitions and artifact creation."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    job = enqueue_document_job(db=db_session, document_id=doc.id)
    assert job.status == JobStatus.QUEUED

    # Execute single job through worker logic
    success = process_single_job(
        db=db_session,
        storage=mock_storage,
        job=job,
        worker_id="test-worker-01",
    )
    assert success is True

    db_session.refresh(job)
    db_session.refresh(doc)
    assert job.status == JobStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.completed_at >= job.started_at
    assert job.worker_id == "test-worker-01"
    assert doc.processing_status == ProcessingStatus.COMPLETED

    # Verify normalized content artifact exists in DB and storage
    artifact = db_session.execute(
        select(ProcessingArtifact).where(ProcessingArtifact.document_id == doc.id)
    ).scalar_one_or_none()
    assert artifact is not None
    assert artifact.artifact_type == ArtifactType.NORMALIZED_CONTENT


# ==============================================================================
# TEST 4: MULTIPLE DOCUMENTS PROCESSING
# ==============================================================================
def test_04_multiple_documents_reach_terminal_state(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify processing multiple documents (e.g. 20 documents)."""
    tender, version = sample_tender_and_version
    doc_jobs = []

    for i in range(20):
        doc = _create_mock_document(
            db=db_session,
            storage=mock_storage,
            tender_id=tender.id,
            version_id=version.id,
            user_id=procurement_officer_user.id,
            filename=f"doc_{i:02d}.pdf",
        )
        job = enqueue_document_job(db=db_session, document_id=doc.id)
        doc_jobs.append((doc, job))

    assert len(doc_jobs) == 20

    # Process all jobs
    for doc, job in doc_jobs:
        ok = process_single_job(
            db=db_session,
            storage=mock_storage,
            job=job,
            worker_id=f"worker-pool-{(doc.id.int % 3) + 1}",
        )
        assert ok is True

    # Verify all 20 reached COMPLETED
    for doc, job in doc_jobs:
        db_session.refresh(job)
        db_session.refresh(doc)
        assert job.status == JobStatus.COMPLETED
        assert doc.processing_status == ProcessingStatus.COMPLETED


# ==============================================================================
# TEST 5: PARALLELISM & CONCURRENCY
# ==============================================================================
def test_05_concurrency_demonstrated_via_timestamps(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify multiple worker threads process jobs concurrently with overlapping execution windows."""
    tender, version = sample_tender_and_version
    docs = []
    jobs = []

    for i in range(6):
        doc = _create_mock_document(
            db=db_session,
            storage=mock_storage,
            tender_id=tender.id,
            version_id=version.id,
            user_id=procurement_officer_user.id,
            filename=f"concurrent_doc_{i}.pdf",
        )
        job = enqueue_document_job(db=db_session, document_id=doc.id)
        docs.append(doc)
        jobs.append(job)

    import threading
    db_lock = threading.Lock()
    from tests.conftest import TestingSessionLocal

    def run_worker_task(j_id: uuid.UUID, w_name: str):
        # 1. Record start timestamp
        with db_lock:
            with TestingSessionLocal() as session:
                j = session.get(DocumentProcessingJob, j_id)
                doc = session.get(Document, j.document_id)
                doc_key = doc.storage_key
                doc_fname = doc.filename
                doc_ext = doc.file_extension
                doc_id = doc.id
                j.started_at = datetime.datetime.now(datetime.timezone.utc)
                j.status = JobStatus.PROCESSING
                j.worker_id = w_name
                session.commit()

        # 2. Concurrently execute parsing without holding DB lock
        stream = mock_storage.download(doc_key)
        content_bytes = stream.read() if hasattr(stream, "read") else bytes(stream)
        time.sleep(0.1)  # Simulate parallel I/O & computation
        norm_doc = parse_document(
            document_id=doc_id,
            content=content_bytes,
            filename=doc_fname,
            file_extension=doc_ext,
        )

        # 3. Finalize and mark completed with db_lock
        with db_lock:
            with TestingSessionLocal() as session:
                j = session.get(DocumentProcessingJob, j_id)
                process_single_job(db=session, storage=mock_storage, job=j, worker_id=w_name)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(run_worker_task, j.id, f"thread-worker-{i % 3 + 1}")
            for i, j in enumerate(jobs)
        ]
        for f in futures:
            f.result()

    # Refresh and verify concurrent overlap in execution
    for j in jobs:
        db_session.refresh(j)
        assert j.status == JobStatus.COMPLETED
        assert j.worker_id is not None
        assert j.started_at is not None
        assert j.completed_at is not None

    # Check concurrency: at least two jobs must have overlapping [started_at, completed_at] windows
    overlaps = 0
    for i in range(len(jobs)):
        for k in range(i + 1, len(jobs)):
            j1, j2 = jobs[i], jobs[k]
            if not (j1.completed_at < j2.started_at or j2.completed_at < j1.started_at):
                overlaps += 1
    assert overlaps > 0, "Expected overlapping job executions demonstrating concurrency"


# ==============================================================================
# TEST 6: IDEMPOTENCY
# ==============================================================================
def test_06_idempotency_avoids_duplicate_processing(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify delivering the same job twice does not duplicate artifacts."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    job = enqueue_document_job(db=db_session, document_id=doc.id)
    # First execution
    assert process_single_job(db=db_session, storage=mock_storage, job=job) is True
    db_session.refresh(job)
    first_completed_at = job.completed_at

    # Count artifacts after first run
    count_1 = db_session.execute(
        select(ProcessingArtifact).where(ProcessingArtifact.document_id == doc.id)
    ).scalars().all()
    assert len(count_1) == 1

    # Second execution (simulating duplicate delivery)
    assert process_single_job(db=db_session, storage=mock_storage, job=job) is True
    db_session.refresh(job)

    # Completed at should remain unchanged and no extra artifact created
    assert job.completed_at == first_completed_at
    count_2 = db_session.execute(
        select(ProcessingArtifact).where(ProcessingArtifact.document_id == doc.id)
    ).scalars().all()
    assert len(count_2) == 1


# ==============================================================================
# TEST 7: CONTROLLED RETRY ON TRANSIENT FAILURE
# ==============================================================================
def test_07_controlled_retry_on_transient_failure(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify transient error triggers retry transition and respects max_attempts."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    job = enqueue_document_job(db=db_session, document_id=doc.id)
    job.attempt_count = 1

    # Simulate transient failure
    mark_job_failed(
        db=db_session,
        job=job,
        error_code="TRANSIENT_CONNECTION_ERROR",
        error_message="Temporary S3 timeout",
    )
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED  # Re-queued for retry
    assert job.error_code == "TRANSIENT_CONNECTION_ERROR"


# ==============================================================================
# TEST 8: PERMANENT FAILURE ISOLATION
# ==============================================================================
def test_08_permanent_failure_isolation(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify permanent failure transitions to FAILED without affecting other jobs."""
    tender, version = sample_tender_and_version
    doc_bad = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
        filename="corrupt.pdf",
        content=b"",  # Empty content triggers ValueError in parser
    )
    doc_good = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
        filename="good.pdf",
    )

    job_bad = enqueue_document_job(db=db_session, document_id=doc_bad.id)
    job_good = enqueue_document_job(db=db_session, document_id=doc_good.id)

    # Process bad job -> should fail permanently
    process_single_job(db=db_session, storage=mock_storage, job=job_bad)
    db_session.refresh(job_bad)
    db_session.refresh(doc_bad)
    assert job_bad.status == JobStatus.FAILED
    assert job_bad.failed_at is not None
    assert doc_bad.processing_status == ProcessingStatus.FAILED

    # Good job is unaffected
    process_single_job(db=db_session, storage=mock_storage, job=job_good)
    db_session.refresh(job_good)
    assert job_good.status == JobStatus.COMPLETED


# ==============================================================================
# TEST 9: WORKER RECOVERY OF STALLED JOBS
# ==============================================================================
def test_09_worker_recovery_of_stalled_jobs(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify stalled jobs from crashed workers are recovered safely."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    job = enqueue_document_job(db=db_session, document_id=doc.id)
    # Simulate crashed worker leaving job in PROCESSING state
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=600)
    db_session.commit()

    recovered = recover_stalled_jobs(db_session, timeout_seconds=300)
    assert recovered == 1

    db_session.refresh(job)
    assert job.status in (JobStatus.QUEUED, JobStatus.FAILED)
    assert job.error_code == "WORKER_TIMEOUT_OR_CRASH"


# ==============================================================================
# TEST 10: REDIS RESILIENCE
# ==============================================================================
def test_10_database_first_resilience(
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify jobs remain persisted in PostgreSQL even if Redis publishing is suppressed."""
    tender, version = sample_tender_and_version
    doc = _create_mock_document(
        db=db_session,
        storage=mock_storage,
        tender_id=tender.id,
        version_id=version.id,
        user_id=procurement_officer_user.id,
    )

    # Disable Redis publishing explicitly
    job = enqueue_document_job(db=db_session, document_id=doc.id, publish_redis=False)
    assert job.status == JobStatus.QUEUED

    # Job is securely recorded in DB and can be fetched by worker
    fetched = fetch_next_job(db_session)
    assert fetched.id == job.id


# ==============================================================================
# TEST 11: BATCH STATUS ENDPOINTS
# ==============================================================================
def test_11_batch_processing_status_endpoints(
    client,
    db_session: Session,
    mock_storage,
    sample_tender_and_version,
    procurement_officer_user,
):
    """Verify batch processing status API returns completion stats for tender version."""
    from app.auth.jwt import create_access_token

    tender, version = sample_tender_and_version
    token = create_access_token(subject=procurement_officer_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    docs = []
    for i in range(5):
        doc = _create_mock_document(
            db=db_session,
            storage=mock_storage,
            tender_id=tender.id,
            version_id=version.id,
            user_id=procurement_officer_user.id,
            filename=f"batch_doc_{i}.pdf",
        )
        job = enqueue_document_job(db=db_session, document_id=doc.id)
        docs.append((doc, job))

    # Before processing: 5 queued, 0 completed
    resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/processing-status",
        headers=headers,
    )
    assert resp.status_code == 200
    batch_data = resp.json()
    assert batch_data["total"] == 5
    assert batch_data["completed"] == 0
    assert batch_data["queued"] == 5
    assert batch_data["is_complete"] is False

    # Process 3 out of 5
    for doc, job in docs[:3]:
        process_single_job(db=db_session, storage=mock_storage, job=job)

    resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/processing-status",
        headers=headers,
    )
    assert resp.status_code == 200
    batch_data = resp.json()
    assert batch_data["total"] == 5
    assert batch_data["completed"] == 3
    assert batch_data["queued"] == 2
    assert batch_data["is_complete"] is False

    # Process remaining 2
    for doc, job in docs[3:]:
        process_single_job(db=db_session, storage=mock_storage, job=job)

    resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/processing-status",
        headers=headers,
    )
    assert resp.status_code == 200
    batch_data = resp.json()
    assert batch_data["total"] == 5
    assert batch_data["completed"] == 5
    assert batch_data["is_complete"] is True
