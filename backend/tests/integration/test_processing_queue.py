"""Integration tests for document processing queue lifecycle and retries."""

import io
import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.pipeline.queue import (
    enqueue_document_job,
    fetch_next_job,
    mark_job_completed,
    mark_job_failed,
)
from app.pipeline.schemas import DocumentPage, NormalizedDocument
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender


@pytest.fixture
def sample_document(db_session: Session, procurement_officer_user) -> Document:
    tender = create_tender(
        db=db_session,
        payload=TenderCreate(
            tender_number=f"CRPF-Q-{uuid.uuid4().hex[:6].upper()}",
            title="Queue Test Tender",
        ),
        user_id=procurement_officer_user.id,
    )
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=tender.active_version.id,
        filename="test_specs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key="documents/test/key.pdf",
        document_type=DocumentType.UNKNOWN,
        processing_status=ProcessingStatus.VALIDATED,
        uploaded_by=procurement_officer_user.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_enqueue_and_fetch_job_lifecycle(db_session: Session, sample_document: Document):
    # 1. Enqueue job
    job = enqueue_document_job(db=db_session, document_id=sample_document.id)
    assert job.status == JobStatus.QUEUED
    assert job.document_id == sample_document.id
    assert job.attempt_count == 0

    # 2. Re-enqueueing returns existing active job (idempotent)
    job_dup = enqueue_document_job(db=db_session, document_id=sample_document.id)
    assert job_dup.id == job.id

    # 3. Fetch next job
    fetched_job = fetch_next_job(db=db_session)
    assert fetched_job is not None
    assert fetched_job.id == job.id
    assert fetched_job.status == JobStatus.PROCESSING
    assert fetched_job.attempt_count == 1
    assert fetched_job.started_at is not None

    # 4. Mark job completed
    norm_doc = NormalizedDocument(
        document_id=sample_document.id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=1,
        total_characters=100,
        total_tables=0,
        pages=[DocumentPage(page_number=1)],
    )
    mark_job_completed(
        db=db_session,
        job=fetched_job,
        normalized_doc=norm_doc,
        artifact_storage_key="documents/test/artifacts/normalized.json",
        artifact_size=500,
    )

    db_session.refresh(fetched_job)
    db_session.refresh(sample_document)
    assert fetched_job.status == JobStatus.COMPLETED
    assert fetched_job.completed_at is not None
    assert sample_document.processing_status == ProcessingStatus.COMPLETED
    assert sample_document.document_type == DocumentType.DIGITAL_PDF


def test_job_failure_retry_and_terminal_exhaustion(db_session: Session, sample_document: Document):
    job = enqueue_document_job(db=db_session, document_id=sample_document.id)
    assert job.max_attempts == 3

    # Attempt 1 -> Fail
    j1 = fetch_next_job(db=db_session)
    assert j1.attempt_count == 1
    mark_job_failed(db=db_session, job=j1, error_code="TIMEOUT", error_message="First timeout")
    db_session.refresh(j1)
    assert j1.status == JobStatus.QUEUED  # re-queued for retry

    # Attempt 2 -> Fail
    j2 = fetch_next_job(db=db_session)
    assert j2.attempt_count == 2
    mark_job_failed(db=db_session, job=j2, error_code="TIMEOUT", error_message="Second timeout")
    db_session.refresh(j2)
    assert j2.status == JobStatus.QUEUED

    # Attempt 3 -> Fail (terminal)
    j3 = fetch_next_job(db=db_session)
    assert j3.attempt_count == 3
    mark_job_failed(db=db_session, job=j3, error_code="PERMANENT_ERROR", error_message="Max attempts reached")
    db_session.refresh(j3)
    db_session.refresh(sample_document)
    assert j3.status == JobStatus.FAILED
    assert j3.completed_at is not None
    assert sample_document.processing_status == ProcessingStatus.FAILED
