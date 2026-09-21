"""Integration tests for partial failure handling and compensatory orphan object cleanup."""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.storage.service import InMemoryObjectStorageService
from app.tenders.schemas import TenderCreate
from app.tenders.service import create_tender


@pytest.fixture
def test_tender(db_session: Session, procurement_officer_user):
    payload = TenderCreate(
        tender_number=f"CRPF-FAIL-{uuid.uuid4().hex[:6].upper()}",
        title="Failure Handling Tender",
        description="Testing partial failure and orphan cleanup",
    )
    return create_tender(
        db=db_session,
        payload=payload,
        user_id=procurement_officer_user.id,
    )


def test_storage_upload_failure_aborts_db_metadata(
    client: TestClient,
    procurement_officer_token: str,
    test_tender,
    memory_storage: InMemoryObjectStorageService,
    monkeypatch,
    db_session: Session,
):
    active_version = test_tender.active_version

    # Force storage.upload to fail
    def failing_upload(*args, **kwargs):
        raise RuntimeError("Simulated S3 connection outage")

    monkeypatch.setattr(memory_storage, "upload", failing_upload)

    pdf_bytes = b"%PDF-1.4 sample content"
    files = {"file": ("tender_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )

    assert response.status_code == 500
    assert "Failed to store document binary" in response.json()["detail"]

    # Verify no documents exist in database
    docs_in_db = db_session.query(Document).filter(Document.tender_id == test_tender.id).all()
    assert len(docs_in_db) == 0


def test_database_failure_triggers_storage_orphan_cleanup(
    client: TestClient,
    procurement_officer_token: str,
    test_tender,
    memory_storage: InMemoryObjectStorageService,
    monkeypatch,
):
    active_version = test_tender.active_version

    deleted_keys = []
    original_delete = memory_storage.delete

    def tracking_delete(key: str) -> bool:
        deleted_keys.append(key)
        return original_delete(key)

    monkeypatch.setattr(memory_storage, "delete", tracking_delete)

    # Force db.commit to raise an exception during metadata persistence
    from sqlalchemy.orm import Session as SASession

    def failing_commit(self):
        raise RuntimeError("Simulated database constraint or write failure")

    monkeypatch.setattr(SASession, "commit", failing_commit)

    pdf_bytes = b"%PDF-1.4 sample content"
    files = {"file": ("tender_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    response = client.post(
        f"/api/v1/tenders/{test_tender.id}/versions/{active_version.id}/documents",
        files=files,
        headers={"Authorization": f"Bearer {procurement_officer_token}"},
    )

    assert response.status_code == 500
    assert "Failed to record document metadata" in response.json()["detail"]

    # Verify orphan cleanup occurred
    assert len(deleted_keys) == 1
    assert memory_storage.exists(deleted_keys[0]) is False
