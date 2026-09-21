"""Integration tests for document ingestion security validations and access control."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender


@pytest.fixture
def test_tender(db_session: Session, procurement_officer_user):
    """Create a tender for security tests."""
    payload = TenderCreate(
        tender_number=f"CRPF-SEC-{uuid.uuid4().hex[:6].upper()}",
        title="Security Validation Tender",
        description="Testing security controls",
    )
    return create_tender(
        db=db_session,
        payload=payload,
        user_id=procurement_officer_user.id,
    )


def test_upload_unauthenticated_rejected(client: TestClient, test_tender):
    active_version = test_tender.active_version
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
    )
    assert response.status_code == 401


def test_upload_reviewer_role_forbidden(client: TestClient, reviewer_token: str, test_tender):
    active_version = test_tender.active_version
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_upload_unsupported_file_extension_rejected(client: TestClient, procurement_officer_token: str, test_tender):
    active_version = test_tender.active_version
    # Attempting to upload a raw zip or executable
    files = {"file": ("archive.zip", io.BytesIO(b"PK\x03\x04dummy"), "application/zip")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_mime_spoofing_rejected(client: TestClient, procurement_officer_token: str, test_tender):
    active_version = test_tender.active_version
    # Executable renamed to .pdf
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00malicious binary content"
    files = {"file": ("tender_document.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 400
    assert "Executable binaries are strictly prohibited" in response.json()["detail"]


def test_upload_path_traversal_filename_rejected(client: TestClient, procurement_officer_token: str, test_tender):
    active_version = test_tender.active_version
    pdf_bytes = b"%PDF-1.4 valid header"
    files = {"file": ("../../../../etc/shadow.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 400
    assert "path traversal" in response.json()["detail"].lower()


def test_upload_nonexistent_tender_returns_404(client: TestClient, procurement_officer_token: str, test_tender):
    random_id = uuid.uuid4()
    pdf_bytes = b"%PDF-1.4 valid header"
    files = {"file": ("tender.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{random_id}/versions/{test_tender.active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 404
    assert "Tender" in response.json()["detail"]


def test_upload_nonexistent_version_returns_404(client: TestClient, procurement_officer_token: str, test_tender):
    random_version_id = uuid.uuid4()
    pdf_bytes = b"%PDF-1.4 valid header"
    files = {"file": ("tender.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{random_version_id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 404
    assert "TenderVersion" in response.json()["detail"]


def test_upload_oversized_file_rejected(client: TestClient, procurement_officer_token: str, test_tender, monkeypatch):
    active_version = test_tender.active_version

    # Temporarily set MAX_UPLOAD_SIZE_MB to a tiny size (e.g. 1 MB) for testing limit enforcement
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    # 1.5 MB payload
    oversized_data = b"%PDF-1.4 " + b"X" * (1024 * 1024 + 500 * 1024)
    files = {"file": ("big_tender.pdf", io.BytesIO(oversized_data), "application/pdf")}

    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response.status_code == 413
    assert "exceeds the maximum permitted limit" in response.json()["detail"]
