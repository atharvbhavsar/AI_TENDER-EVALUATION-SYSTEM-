"""Unit tests for Phase 16 Document Integrity Verification."""

import hashlib
import io
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit.events import AuditAction
from app.audit.schemas import AuditLogFilter, IntegrityStatus
from app.audit.service import AuditService
from app.db.base import Base
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.documents.integrity import compute_sha256_from_stream, verify_document_integrity
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session fixture for document integrity tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def storage():
    """In-memory storage service."""
    return InMemoryObjectStorageService()


def create_mock_document(db: Session, storage: InMemoryObjectStorageService, content: bytes = b"CRPF Procurement Binary Content") -> Document:
    """Helper to create a persisted document and upload its binary to storage."""
    user = User(
        id=uuid.uuid4(),
        email=f"officer_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        password_hash="hash",
        full_name="Evaluation Officer",
    )
    db.add(user)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF/TND/{uuid.uuid4().hex[:6]}",
        title="Procurement Tender",
        created_by=user.id,
        status=TenderStatus.DRAFT,
    )
    db.add(tender)

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=user.id,
    )
    db.add(version)

    sha256_hash = hashlib.sha256(content).hexdigest()
    storage_key = f"tenders/{tender.id}/v1/{uuid.uuid4()}.pdf"

    storage.upload(storage_key, io.BytesIO(content), "application/pdf")

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="tender_spec.pdf",
        content_type="application/pdf",
        file_extension="pdf",
        file_size=len(content),
        sha256_hash=sha256_hash,
        storage_key=storage_key,
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_compute_sha256_from_stream():
    """Verify stream SHA-256 computation."""
    content = b"CRPF Technical Specification 2026"
    expected = hashlib.sha256(content).hexdigest()
    calculated = compute_sha256_from_stream(io.BytesIO(content))
    assert calculated == expected


def test_verify_document_integrity_verified_success(db_session: Session, storage: InMemoryObjectStorageService):
    """Verify document integrity check matches and records DOCUMENT_INTEGRITY_CHECKED."""
    doc = create_mock_document(db_session, storage, b"Valid Official Procurement Doc")

    result = verify_document_integrity(db_session, doc.id, storage)
    db_session.commit()

    assert result.integrity_status == IntegrityStatus.VERIFIED
    assert result.stored_sha256 == doc.sha256_hash
    assert result.computed_sha256 == doc.sha256_hash
    assert "verified" in result.message.lower()

    # Check audit log recorded
    logs, total = AuditService.query_logs(
        db_session,
        AuditLogFilter(document_id=doc.id, action=AuditAction.DOCUMENT_INTEGRITY_CHECKED.value),
    )
    assert total >= 1
    assert logs[0].metadata_json["integrity_status"] == "VERIFIED"


def test_verify_document_integrity_mismatch_detected(db_session: Session, storage: InMemoryObjectStorageService):
    """Verify document tampering is detected as MISMATCH without overwriting stored hash."""
    doc = create_mock_document(db_session, storage, b"Original Unmodified Binary")
    original_hash = doc.sha256_hash

    # Tamper with storage binary
    tampered_content = b"Tampered Malicious Document Content"
    storage.upload(doc.storage_key, io.BytesIO(tampered_content), "application/pdf")

    result = verify_document_integrity(db_session, doc.id, storage)
    db_session.commit()

    assert result.integrity_status == IntegrityStatus.MISMATCH
    assert result.stored_sha256 == original_hash
    assert result.computed_sha256 == hashlib.sha256(tampered_content).hexdigest()
    assert result.stored_sha256 != result.computed_sha256

    # Verify stored hash was NOT overwritten in database
    db_session.refresh(doc)
    assert doc.sha256_hash == original_hash

    # Check audit log recorded DOCUMENT_INTEGRITY_MISMATCH
    logs, total = AuditService.query_logs(
        db_session,
        AuditLogFilter(document_id=doc.id, action=AuditAction.DOCUMENT_INTEGRITY_MISMATCH.value),
    )
    assert total == 1
    assert logs[0].metadata_json["integrity_status"] == "MISMATCH"
    assert logs[0].metadata_json["stored_sha256"] == original_hash
    assert logs[0].metadata_json["computed_sha256"] == hashlib.sha256(tampered_content).hexdigest()


def test_verify_document_integrity_unavailable_storage(db_session: Session, storage: InMemoryObjectStorageService):
    """Verify document integrity when storage object is missing."""
    doc = create_mock_document(db_session, storage, b"Some Binary")
    # Delete binary from storage
    storage.delete(doc.storage_key)

    result = verify_document_integrity(db_session, doc.id, storage)
    db_session.commit()

    assert result.integrity_status == IntegrityStatus.UNAVAILABLE
    assert result.computed_sha256 is None
    assert "unavailable" in result.message.lower()
