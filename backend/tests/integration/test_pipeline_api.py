"""Integration tests for document processing API endpoints and permissions."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import Document, ProcessingStatus
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender
from app.workers.document_worker import process_single_job
from app.storage.service import InMemoryObjectStorageService
from tests.unit.test_pdf_parser import make_sample_pdf


@pytest.fixture
def processed_document(
    client: TestClient,
    procurement_officer_token: str,
    db_session: Session,
    procurement_officer_user,
    memory_storage: InMemoryObjectStorageService,
):
    tender = create_tender(
        db=db_session,
        payload=TenderCreate(
            tender_number=f"CRPF-API-{uuid.uuid4().hex[:6].upper()}",
            title="API Test Tender",
        ),
        user_id=procurement_officer_user.id,
    )
    pdf_bytes = make_sample_pdf("CRPF Tender API Specifications Content")
    files = {"file": ("api_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    upload_resp = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{tender.active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    doc_id = uuid.UUID(upload_resp.json()["id"])
    
    # Process the job
    from app.db.models.document_job import DocumentProcessingJob, JobStatus
    job = db_session.query(DocumentProcessingJob).filter(DocumentProcessingJob.document_id == doc_id).first()
    job.status = JobStatus.PROCESSING
    db_session.commit()
    process_single_job(db=db_session, storage=memory_storage, job=job)

    return doc_id


def test_get_processing_status_success(client: TestClient, reviewer_token: str, processed_document: uuid.UUID):
    response = client.get(
        f"/api/v1/documents/{processed_document}/processing-status",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == str(processed_document)
    assert data["status"] == "COMPLETED"
    assert data["processor_version"] == "1.0.0"


def test_get_processing_status_not_found(client: TestClient, reviewer_token: str):
    response = client.get(
        f"/api/v1/documents/{uuid.uuid4()}/processing-status",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 404


def test_get_content_unauthenticated_rejected(client: TestClient, processed_document: uuid.UUID):
    response = client.get(f"/api/v1/documents/{processed_document}/content")
    assert response.status_code == 401


def test_trigger_reprocess_endpoint(client: TestClient, procurement_officer_token: str, processed_document: uuid.UUID):
    response = client.post(
        f"/api/v1/documents/{processed_document}/process",
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "QUEUED"
    assert "job_id" in data


def test_trigger_reprocess_reviewer_forbidden(client: TestClient, reviewer_token: str, processed_document: uuid.UUID):
    # Reviewer does not have DOCUMENT_UPLOAD
    response = client.post(
        f"/api/v1/documents/{processed_document}/process",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403
