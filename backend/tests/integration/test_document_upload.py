"""Integration tests for authorized procurement document upload."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender
from app.storage.service import InMemoryObjectStorageService
from tests.unit.test_file_validation import create_dummy_docx_bytes, create_dummy_xlsx_bytes


@pytest.fixture
def test_tender(db_session: Session, procurement_officer_user):
    """Create a tender with Version 1 for document upload tests."""
    payload = TenderCreate(
        tender_number=f"CRPF-DOC-TEST-{uuid.uuid4().hex[:6].upper()}",
        title="Procurement of Tactical Gear",
        description="Detailed specs for CRPF equipment",
    )
    return create_tender(
        db=db_session,
        payload=payload,
        user_id=procurement_officer_user.id,
    )


def test_upload_valid_pdf_success(client: TestClient, procurement_officer_token: str, test_tender, memory_storage: InMemoryObjectStorageService):
    active_version = test_tender.active_version
    assert active_version is not None

    pdf_content = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF"
    files = {
        "file": ("crpf_tactical_specs.pdf", io.BytesIO(pdf_content), "application/pdf")
    }

    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "crpf_tactical_specs.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["file_extension"] == ".pdf"
    assert data["file_size"] == len(pdf_content)
    assert "sha256_hash" in data
    assert data["storage_key"].startswith(f"documents/tender/{test_tender.id}/version/{active_version.id}/")
    assert data["document_type"] == "UNKNOWN"
    assert data["processing_status"] == "VALIDATED"

    # Verify binary exists in storage
    assert memory_storage.exists(data["storage_key"]) is True
    downloaded = memory_storage.download(data["storage_key"]).read()
    assert downloaded == pdf_content


def test_upload_valid_docx_and_xlsx_success(client: TestClient, procurement_officer_token: str, test_tender, memory_storage: InMemoryObjectStorageService):
    active_version = test_tender.active_version

    # 1. DOCX
    docx_bytes = create_dummy_docx_bytes()
    response_docx = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files={"file": ("tender_contract.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response_docx.status_code == 201
    assert response_docx.json()["file_extension"] == ".docx"

    # 2. XLSX
    xlsx_bytes = create_dummy_xlsx_bytes()
    response_xlsx = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files={"file": ("tender_boq.xlsx", io.BytesIO(xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert response_xlsx.status_code == 201
    assert response_xlsx.json()["file_extension"] == ".xlsx"


def test_upload_valid_images_success(client: TestClient, procurement_officer_token: str, test_tender, memory_storage: InMemoryObjectStorageService):
    active_version = test_tender.active_version

    # JPEG
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 20
    resp_jpeg = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files={"file": ("site_photo.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert resp_jpeg.status_code == 201
    assert resp_jpeg.json()["file_extension"] == ".jpg"

    # PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    resp_png = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files={"file": ("equipment_diagram.png", io.BytesIO(png_bytes), "image/png")},
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )
    assert resp_png.status_code == 201
    assert resp_png.json()["file_extension"] == ".png"
