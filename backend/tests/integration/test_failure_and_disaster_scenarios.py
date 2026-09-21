"""Integration tests for Disaster, Failure, and Recovery Scenarios."""

import datetime
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.db.base import Base
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.pipeline.queue import recover_stalled_jobs


@pytest.fixture
def db_session():
    """In-memory SQLite session for testing disaster and recovery workflows."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_stalled_worker_job_recovery_on_crash(db_session: Session):
    """Verify jobs stuck in PROCESSING state due to worker crashes are recovered."""
    # 1. Create user, tender, doc
    officer = User(
        id=uuid.uuid4(),
        email="officer_disaster@crpf.gov.in",
        password_hash="hash",
        full_name="Procurement Officer Disaster",
        is_active=True,
    )
    db_session.add(officer)
    db_session.flush()

    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF-DISASTER-01",
        title="Disaster Recovery Test Tender",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="corrupted_scan.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key="test/corrupted_scan.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.PROCESSING,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    # 2. Simulate job started 300 seconds ago (stalled due to worker process kill)
    stalled_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=300)
    job = DocumentProcessingJob(
        id=uuid.uuid4(),
        document_id=doc.id,
        status=JobStatus.PROCESSING,
        attempt_count=1,
        max_attempts=3,
        processor_version="1.0.0",
        started_at=stalled_time,
    )
    db_session.add(job)
    db_session.commit()

    # 3. Trigger recovery with 120s timeout
    recovered_count = recover_stalled_jobs(db_session, timeout_seconds=120)
    assert recovered_count == 1

    # 4. Verify job is re-queued for retry
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED
    assert job.error_code == "WORKER_TIMEOUT_OR_CRASH"

    # 5. If job exceeds max_attempts on next stall, it should permanently fail
    job.attempt_count = 3
    job.status = JobStatus.PROCESSING
    job.started_at = stalled_time
    db_session.commit()

    recovered_again = recover_stalled_jobs(db_session, timeout_seconds=120)
    assert recovered_again == 1
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED
