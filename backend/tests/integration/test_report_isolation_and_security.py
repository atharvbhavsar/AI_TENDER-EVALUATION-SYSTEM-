"""Security and Isolation tests for Phase 14 Reporting and Audit APIs."""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.role import Role
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import set_storage_service_override


@pytest.fixture
def security_fixture(db_session):
    """Setup dual tender/version/bidder fixture for isolation and security testing."""
    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)

    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    # User 1: Authorized Officer
    user_officer = User(
        id=uuid.uuid4(),
        email=f"officer_sec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Authorized Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        user_officer.roles.append(officer_role)

    # User 2: Plain unprivileged user without evaluation/report permissions
    user_plain = User(
        id=uuid.uuid4(),
        email=f"plain_user_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Plain User",
        is_active=True,
        password_hash="dummy_hash",
    )
    db_session.add_all([user_officer, user_plain])

    # Tender 1, Version 1
    tender1 = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-SEC-1-{uuid.uuid4().hex[:4]}",
        title="Tender 1",
        status=TenderStatus.PUBLISHED,
        created_by=user_officer.id,
    )
    db_session.add(tender1)
    db_session.flush()

    v1 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        version_number=1,
        created_by=user_officer.id,
    )
    v2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        version_number=2,
        created_by=user_officer.id,
    )
    db_session.add_all([v1, v2])
    db_session.flush()

    # Bidder A on Version 1
    bidder_a = Bidder(id=uuid.uuid4(), tender_id=tender1.id, bidder_code="B01", legal_name="Bidder Alpha")
    bidder_b = Bidder(id=uuid.uuid4(), tender_id=tender1.id, bidder_code="B02", legal_name="Bidder Beta")
    db_session.add_all([bidder_a, bidder_b])
    db_session.flush()


    sub_a = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder_a.id, submission_reference="SUB-A")
    sub_b = BidSubmission(id=uuid.uuid4(), tender_version_id=v2.id, bidder_id=bidder_b.id, submission_reference="SUB-B")
    db_session.add_all([sub_a, sub_b])
    db_session.flush()


    # Report for Sub A (Version 1)
    rep_a = EvaluationReport(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        report_type=ReportType.BIDDER_EVALUATION_REPORT,
        report_version=1,
        status=ReportStatus.COMPLETED,
        title="Bidder Alpha Report",
        mime_type="application/pdf",
        storage_key=f"reports/{tender1.id}/{v1.id}/bidder/{sub_a.id}_v1.pdf",
        file_hash="aa" * 32,
    )
    db_session.add(rep_a)
    db_session.commit()

    # Pre-upload mock pdf in memory storage
    mem_storage.upload(rep_a.storage_key, b"%PDF-1.4 Mock Alpha PDF Content")

    token_officer = create_access_token(user_officer.id)
    token_plain = create_access_token(user_plain.id)


    yield {
        "headers_officer": {"Authorization": f"Bearer {token_officer}"},
        "headers_plain": {"Authorization": f"Bearer {token_plain}"},
        "tender1": tender1,
        "v1": v1,
        "v2": v2,
        "sub_a": sub_a,
        "sub_b": sub_b,
        "rep_a": rep_a,
    }

    set_storage_service_override(None)


def test_unauthenticated_access_blocked(client: TestClient, security_fixture):
    """Verify all report and audit endpoints reject unauthenticated requests with 401."""
    rep_a = security_fixture["rep_a"]
    sub_a = security_fixture["sub_a"]

    assert client.get(f"/api/v1/reports/{rep_a.id}").status_code == 401
    assert client.get(f"/api/v1/reports/{rep_a.id}/download").status_code == 401
    assert client.get(f"/api/v1/submissions/{sub_a.id}/explanation").status_code == 401
    assert client.get(f"/api/v1/submissions/{sub_a.id}/audit").status_code == 401
    assert client.post(f"/api/v1/submissions/{sub_a.id}/reports").status_code == 401
    assert client.get("/api/v1/audit/logs").status_code == 401


def test_rbac_unauthorized_user_forbidden(client: TestClient, security_fixture):
    """Verify users without REPORT_READ/EVALUATION_READ permissions receive 403."""
    headers_plain = security_fixture["headers_plain"]
    rep_a = security_fixture["rep_a"]
    sub_a = security_fixture["sub_a"]

    assert client.get(f"/api/v1/reports/{rep_a.id}", headers=headers_plain).status_code == 403
    assert client.get(f"/api/v1/reports/{rep_a.id}/download", headers=headers_plain).status_code == 403
    assert client.get(f"/api/v1/submissions/{sub_a.id}/explanation", headers=headers_plain).status_code == 403
    assert client.post(f"/api/v1/submissions/{sub_a.id}/reports", headers=headers_plain).status_code == 403
    assert client.get("/api/v1/audit/logs", headers=headers_plain).status_code == 403


def test_idor_nonexistent_report_returns_404(client: TestClient, security_fixture):
    """Verify requesting a non-existent report ID returns 404 without leaking server details."""
    headers_officer = security_fixture["headers_officer"]
    fake_id = uuid.uuid4()

    res = client.get(f"/api/v1/reports/{fake_id}", headers=headers_officer)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_version_isolation_in_reports_listing(client: TestClient, security_fixture):
    """Verify reports generated for Version 1 do not appear in Version 2 listings."""
    headers_officer = security_fixture["headers_officer"]
    tender1 = security_fixture["tender1"]
    v1 = security_fixture["v1"]
    v2 = security_fixture["v2"]

    # Listing for Version 1 should contain rep_a
    res1 = client.get(f"/api/v1/tenders/{tender1.id}/versions/{v1.id}/reports", headers=headers_officer)
    assert res1.status_code == 200
    items_v1 = res1.json()["items"]
    assert any(r["id"] == str(security_fixture["rep_a"].id) for r in items_v1)

    # Listing for Version 2 should NOT contain rep_a
    res2 = client.get(f"/api/v1/tenders/{tender1.id}/versions/{v2.id}/reports", headers=headers_officer)
    assert res2.status_code == 200
    items_v2 = res2.json()["items"]
    assert not any(r["id"] == str(security_fixture["rep_a"].id) for r in items_v2)
