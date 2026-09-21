"""Integration tests for end-to-end asynchronous processing pipeline."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import Document, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.storage.service import InMemoryObjectStorageService
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender
from app.workers.document_worker import process_single_job
from tests.unit.test_pdf_parser import make_sample_pdf


@pytest.fixture
def test_tender(db_session: Session, procurement_officer_user):
    payload = TenderCreate(
        tender_number=f"CRPF-ASYNC-{uuid.uuid4().hex[:6].upper()}",
        title="Async Pipeline Test Tender",
    )
    return create_tender(
        db=db_session,
        payload=payload,
        user_id=procurement_officer_user.id,
    )


def test_e2e_async_document_processing_pipeline(
    client: TestClient,
    procurement_officer_token: str,
    test_tender,
    memory_storage: InMemoryObjectStorageService,
    db_session: Session,
):
    version = test_tender.active_version
    pdf_bytes = make_sample_pdf("CRPF ARMOR TENDER\nMandatory Requirement: Level IV ballistic plates.")
    files = {"file": ("armor_spec.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    # 1. Upload file (Non-blocking upload)
    upload_resp = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()
    doc_id = uuid.UUID(doc_data["id"])

    # 2. Verify job was automatically enqueued
    job = (
        db_session.query(DocumentProcessingJob)
        .filter(DocumentProcessingJob.document_id == doc_id)
        .first()
    )
    assert job is not None
    assert job.status in (JobStatus.QUEUED, JobStatus.PROCESSING)

    # 3. Worker executes the job
    job.status = JobStatus.PROCESSING
    db_session.commit()

    success = process_single_job(db=db_session, storage=memory_storage, job=job)
    assert success is True

    # 4. Verify job and document statuses updated to COMPLETED
    db_session.refresh(job)
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert job.status == JobStatus.COMPLETED
    assert doc.processing_status == ProcessingStatus.COMPLETED
    assert doc.document_type.value == "DIGITAL_PDF"
    assert len(doc.artifacts) >= 1

    # 5. Retrieve structured content via API
    content_resp = client.get(
        f"/api/v1/documents/{doc_id}/content",
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert content_resp.status_code == 200
    norm_content = content_resp.json()
    assert norm_content["document_id"] == str(doc_id)
    assert norm_content["page_count"] == 1
    assert len(norm_content["pages"][0]["blocks"]) >= 1


def test_processing_idempotency(
    client: TestClient,
    procurement_officer_token: str,
    test_tender,
    memory_storage: InMemoryObjectStorageService,
    db_session: Session,
):
    version = test_tender.active_version
    pdf_bytes = make_sample_pdf("CRPF Idempotency Test Content")
    files = {"file": ("idempotent_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    upload_resp = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    doc_id = uuid.UUID(upload_resp.json()["id"])
    job = db_session.query(DocumentProcessingJob).filter(DocumentProcessingJob.document_id == doc_id).first()

    # Process 1st time
    job.status = JobStatus.PROCESSING
    db_session.commit()
    assert process_single_job(db=db_session, storage=memory_storage, job=job) is True

    # Process 2nd time (retry/re-process)
    job.status = JobStatus.PROCESSING
    db_session.commit()
    assert process_single_job(db=db_session, storage=memory_storage, job=job) is True

    # Verify original file remains intact and downloadable
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert memory_storage.exists(doc.storage_key) is True
    assert memory_storage.download(doc.storage_key).read() == pdf_bytes
