"""Integration tests for Phase 16 Audit, Document Integrity, and Provenance APIs."""

import hashlib
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit.events import AuditAction
from app.audit.service import AuditService
from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.permission import Permission
from app.db.models.role import Role
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import get_storage_service


@pytest.fixture
def mock_storage():
    """Shared in-memory storage."""
    return InMemoryObjectStorageService()


@pytest.fixture
def test_setup(client: TestClient, db_session: Session, mock_storage: InMemoryObjectStorageService):
    """Setup roles, users, and override storage dependency."""
    from app.main import app
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    # Retrieve or assign seeded roles
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    auditor_role = db_session.query(Role).filter_by(name="ADMIN").first() or officer_role

    auditor_user = User(
        id=uuid.uuid4(),
        email="auditor_test@crpf.gov.in",
        password_hash="hash",
        full_name="Chief Auditor",
    )
    if auditor_role:
        auditor_user.roles.append(auditor_role)
    db_session.add(auditor_user)

    # Create Bidder User without officer permissions
    bidder_role = db_session.query(Role).filter_by(name="BIDDER").first()

    bidder_user = User(
        id=uuid.uuid4(),
        email="bidder_test@vendor.in",
        password_hash="hash",
        full_name="Vendor User",
    )
    if bidder_role:
        bidder_user.roles.append(bidder_role)
    db_session.add(bidder_user)

    # Create Tender, Version, Bidder, Submission
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF/INT/{uuid.uuid4().hex[:6]}",
        title="Integration Tender Test",
        created_by=auditor_user.id,
        status=TenderStatus.PUBLISHED,
    )
    db_session.add(tender)

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=auditor_user.id,
    )
    db_session.add(version)

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BID-INT-01",
        legal_name="Integration Vendor Corp",
        contact_email="vendor@corp.in",
    )
    db_session.add(bidder)

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-INT-01",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)

    # Create Document and put binary in storage
    doc_content = b"PDF Tender Document Content 12345"
    doc_hash = hashlib.sha256(doc_content).hexdigest()
    storage_key = f"tenders/{tender.id}/v1/{uuid.uuid4()}.pdf"
    mock_storage.upload(storage_key, io.BytesIO(doc_content), "application/pdf")

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Integration_Doc.pdf",
        content_type="application/pdf",
        file_extension="pdf",
        file_size=len(doc_content),
        sha256_hash=doc_hash,
        storage_key=storage_key,
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=auditor_user.id,
    )
    db_session.add(document)

    db_session.commit()

    auditor_token = create_access_token(subject=auditor_user.id)
    bidder_token = create_access_token(subject=bidder_user.id)

    return {
        "auditor_user": auditor_user,
        "auditor_token": auditor_token,
        "bidder_user": bidder_user,
        "bidder_token": bidder_token,
        "tender": tender,
        "version": version,
        "bidder": bidder,
        "submission": submission,
        "document": document,
        "doc_content": doc_content,
        "storage_key": storage_key,
        "mock_storage": mock_storage,
    }


def test_audit_logs_query_and_pagination(client: TestClient, db_session: Session, test_setup):
    """Verify querying audit logs via API with filtering and pagination."""
    token = test_setup["auditor_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Record 3 events
    AuditService.record(
        db_session,
        action=AuditAction.TENDER_CREATED.value,
        entity_type="TENDER",
        entity_id=str(test_setup["tender"].id),
        tender_id=test_setup["tender"].id,
    )
    AuditService.record(
        db_session,
        action=AuditAction.DOCUMENT_UPLOADED.value,
        entity_type="DOCUMENT",
        entity_id=str(test_setup["document"].id),
        tender_id=test_setup["tender"].id,
        document_id=test_setup["document"].id,
    )
    AuditService.record(
        db_session,
        action=AuditAction.DOCUMENT_INTEGRITY_CHECKED.value,
        entity_type="DOCUMENT",
        entity_id=str(test_setup["document"].id),
        tender_id=test_setup["tender"].id,
        document_id=test_setup["document"].id,
    )
    db_session.commit()

    # Query all
    response = client.get(
        f"/api/v1/audit/logs?tender_id={test_setup['tender'].id}&limit=10&offset=0",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Query with action filter
    response_filter = client.get(
        f"/api/v1/audit/logs?action=DOCUMENT_UPLOADED",
        headers=headers,
    )
    assert response_filter.status_code == 200
    filter_data = response_filter.json()
    assert filter_data["total"] == 1
    assert filter_data["items"][0]["action"] == "DOCUMENT_UPLOADED"


def test_get_single_audit_log_by_id(client: TestClient, db_session: Session, test_setup):
    """Verify retrieving a single audit record by UUID."""
    token = test_setup["auditor_token"]
    headers = {"Authorization": f"Bearer {token}"}

    log = AuditService.record(
        db_session,
        action=AuditAction.BIDDER_EVALUATED.value,
        entity_type="BID_SUBMISSION",
        entity_id=str(test_setup["submission"].id),
        bid_submission_id=test_setup["submission"].id,
    )
    db_session.commit()

    response = client.get(f"/api/v1/audit/logs/{log.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(log.id)
    assert data["action"] == "BIDDER_EVALUATED"


def test_tender_and_document_audit_trails(client: TestClient, db_session: Session, test_setup):
    """Verify tender and document specific audit trail endpoints."""
    token = test_setup["auditor_token"]
    headers = {"Authorization": f"Bearer {token}"}

    tender_id = test_setup["tender"].id
    doc_id = test_setup["document"].id

    AuditService.record(
        db_session,
        action="TENDER_VERSION_PUBLISHED",
        entity_type="TENDER_VERSION",
        tender_id=tender_id,
    )
    AuditService.record(
        db_session,
        action="DOCUMENT_ACCESSED",
        entity_type="DOCUMENT",
        document_id=doc_id,
    )
    db_session.commit()

    # Tender audit
    resp_t = client.get(f"/api/v1/audit/tenders/{tender_id}", headers=headers)
    assert resp_t.status_code == 200
    assert resp_t.json()["total"] >= 1

    # Document audit
    resp_d = client.get(f"/api/v1/audit/documents/{doc_id}", headers=headers)
    assert resp_d.status_code == 200
    assert resp_d.json()["total"] >= 1


def test_document_verify_integrity_api_endpoint(client: TestClient, test_setup):
    """Verify POST /api/v1/documents/{doc_id}/verify-integrity."""
    token = test_setup["auditor_token"]
    headers = {"Authorization": f"Bearer {token}"}
    doc = test_setup["document"]

    # 1. Successful verification
    response = client.post(f"/api/v1/documents/{doc.id}/verify-integrity", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["integrity_status"] == "VERIFIED"
    assert data["stored_sha256"] == doc.sha256_hash
    assert data["computed_sha256"] == doc.sha256_hash

    # 2. Tampering test
    mock_storage = test_setup["mock_storage"]
    tampered_bytes = b"Corrupted Modified Binary Payload"
    mock_storage.upload(test_setup["storage_key"], io.BytesIO(tampered_bytes), "application/pdf")

    resp_tampered = client.post(f"/api/v1/documents/{doc.id}/verify-integrity", headers=headers)
    assert resp_tampered.status_code == 200
    tampered_data = resp_tampered.json()
    assert tampered_data["integrity_status"] == "MISMATCH"
    assert tampered_data["stored_sha256"] == doc.sha256_hash
    assert tampered_data["computed_sha256"] == hashlib.sha256(tampered_bytes).hexdigest()


def test_submission_provenance_api_endpoint(client: TestClient, test_setup):
    """Verify GET /api/v1/audit/provenance/submissions/{submission_id}."""
    token = test_setup["auditor_token"]
    headers = {"Authorization": f"Bearer {token}"}
    sub = test_setup["submission"]

    response = client.get(f"/api/v1/audit/provenance/submissions/{sub.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["submission_id"] == str(sub.id)
    assert data["tender_title"] == "Integration Tender Test"
    assert len(data["documents"]) == 1
    assert data["documents"][0]["filename"] == "Integration_Doc.pdf"


def test_audit_rbac_authorization_rejection(client: TestClient, test_setup):
    """Verify unauthorized users (unauthenticated or lacking AUDIT_READ) are rejected."""
    # 1. Unauthenticated request
    assert client.get("/api/v1/audit/logs").status_code == 401

    # 2. Authenticated but insufficient permission (BIDDER)
    bidder_headers = {"Authorization": f"Bearer {test_setup['bidder_token']}"}
    assert client.get("/api/v1/audit/logs", headers=bidder_headers).status_code == 403
    assert client.get(f"/api/v1/audit/submissions/{test_setup['submission'].id}", headers=bidder_headers).status_code == 403
