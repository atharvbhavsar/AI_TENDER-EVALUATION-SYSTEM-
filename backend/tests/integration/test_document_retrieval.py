"""Integration tests for document metadata retrieval and secure download streaming."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender


@pytest.fixture
def uploaded_document(client: TestClient, procurement_officer_token: str, db_session: Session, procurement_officer_user):
    """Fixture uploading a document and returning (tender, version, doc_data, raw_bytes)."""
    payload = TenderCreate(
        tender_number=f"CRPF-RET-{uuid.uuid4().hex[:6].upper()}",
        title="Retrieval Test Tender",
        description="Testing download and metadata",
    )
    tender = create_tender(
        db=db_session,
        payload=payload,
        user_id=procurement_officer_user.id,
    )
    version = tender.active_version
    pdf_bytes = b"%PDF-1.4\nSample Document Content for CRPF\n%%EOF"

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/documents",
        files={"file": ("crpf_manual.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 201
    return tender, version, response.json(), pdf_bytes


def test_get_document_metadata_success(client: TestClient, reviewer_token: str, uploaded_document):
    _, _, doc_data, _ = uploaded_document
    doc_id = doc_data["id"]

    # Reviewer has DOCUMENT_READ
    response = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 200
    retrieved = response.json()
    assert retrieved["id"] == doc_id
    assert retrieved["filename"] == "crpf_manual.pdf"
    assert retrieved["file_extension"] == ".pdf"
    assert retrieved["sha256_hash"] == doc_data["sha256_hash"]


def test_get_document_metadata_not_found(client: TestClient, reviewer_token: str):
    random_id = uuid.uuid4()
    response = client.get(
        f"/api/v1/documents/{random_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 404


def test_download_document_stream_success(client: TestClient, reviewer_token: str, uploaded_document):
    _, _, doc_data, original_bytes = uploaded_document
    doc_id = doc_data["id"]

    response = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="crpf_manual.pdf"' in response.headers["content-disposition"]
    assert response.content == original_bytes


def test_download_document_unauthenticated_rejected(client: TestClient, uploaded_document):
    _, _, doc_data, _ = uploaded_document
    doc_id = doc_data["id"]

    response = client.get(f"/api/v1/documents/{doc_id}/download")
    assert response.status_code == 401


def test_list_tender_version_documents(client: TestClient, reviewer_token: str, uploaded_document):
    tender, version, doc_data, _ = uploaded_document

    response = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/documents",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == doc_data["id"]
