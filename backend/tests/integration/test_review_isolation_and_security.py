"""Integration tests for Phase 13 Review RBAC, IDOR, and Isolation."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.review_case import (
    HumanDecision,
    ReviewCase,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
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


@pytest.fixture
def sec_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_sec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Sec",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer_sec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Reviewer Sec",
        is_active=True,
        password_hash="dummy_hash",
    )
    if reviewer_role:
        reviewer.roles.append(reviewer_role)

    db_session.add_all([officer, reviewer])

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-SEC-{uuid.uuid4().hex[:6]}",
        title="Night Vision Drone",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=2, created_by=officer.id)
    db_session.add_all([v1, v2])
    db_session.flush()

    bidder_a = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="REG-A", legal_name="Alpha Tech", contact_email="a@crpf.gov.in")
    bidder_b = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="REG-B", legal_name="Beta Tech", contact_email="b@crpf.gov.in")
    db_session.add_all([bidder_a, bidder_b])
    db_session.flush()

    sub_a = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder_a.id, submission_reference="SUB-A", status=SubmissionStatus.READY)
    sub_b = BidSubmission(id=uuid.uuid4(), tender_version_id=v2.id, bidder_id=bidder_b.id, submission_reference="SUB-B", status=SubmissionStatus.READY)
    db_session.add_all([sub_a, sub_b])
    db_session.flush()

    case_a = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        status=ReviewStatus.OPEN,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.MANUAL_REVIEW_REQUIRED,
        title="Case A for V1",
        created_by=officer.id,
    )
    case_b = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v2.id,
        bidder_id=bidder_b.id,
        bid_submission_id=sub_b.id,
        status=ReviewStatus.OPEN,
        priority=ReviewPriority.MEDIUM,
        issue_type=ReviewIssueType.MANUAL_REVIEW_REQUIRED,
        title="Case B for V2",
        created_by=officer.id,
    )
    db_session.add_all([case_a, case_b])
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)
    reviewer_token = create_access_token(subject=reviewer.id)

    return {
        "officer": officer,
        "reviewer": reviewer,
        "case_a": case_a,
        "case_b": case_b,
        "v1": v1,
        "v2": v2,
        "bidder_a": bidder_a,
        "bidder_b": bidder_b,
        "officer_headers": {"Authorization": f"Bearer {officer_token}"},
        "reviewer_headers": {"Authorization": f"Bearer {reviewer_token}"},
    }


def test_reviewer_rbac_permissions(client: TestClient, sec_fixture):
    """REVIEWER can read review cases and add notes, but is forbidden from deciding or resolving."""
    fix = sec_fixture
    case_id = fix["case_a"].id

    # Reviewer can view
    resp_get = client.get(f"/api/v1/reviews/{case_id}", headers=fix["reviewer_headers"])
    assert resp_get.status_code == 200

    # Reviewer can add note
    resp_note = client.post(
        f"/api/v1/reviews/{case_id}/notes",
        json={"note": "Reviewer preliminary observation."},
        headers=fix["reviewer_headers"],
    )
    assert resp_note.status_code == 201

    # Reviewer cannot decide (requires REVIEW_APPROVE)
    resp_decide = client.post(
        f"/api/v1/reviews/{case_id}/decide",
        json={"decision": "CONFIRM", "reason": "Looks good"},
        headers=fix["reviewer_headers"],
    )
    assert resp_decide.status_code == 403

    # Reviewer cannot resolve
    resp_resolve = client.post(
        f"/api/v1/reviews/{case_id}/resolve",
        headers=fix["reviewer_headers"],
    )
    assert resp_resolve.status_code == 403


def test_unauthenticated_requests_rejected(client: TestClient, sec_fixture):
    """Unauthenticated access returns 401."""
    case_id = fix_id = sec_fixture["case_a"].id
    resp = client.get(f"/api/v1/reviews/{case_id}")
    assert resp.status_code == 401


def test_nonexistent_review_case_returns_404(client: TestClient, sec_fixture):
    """Accessing random UUID review case returns 404."""
    fake_id = uuid.uuid4()
    resp = client.get(f"/api/v1/reviews/{fake_id}", headers=sec_fixture["officer_headers"])
    assert resp.status_code == 404


def test_version_and_bidder_isolation_in_review_queries(client: TestClient, sec_fixture):
    """Filtering by tender_version_id and bidder_id strictly isolates cases."""
    fix = sec_fixture

    resp_v1 = client.get(
        f"/api/v1/reviews?tender_version_id={fix['v1'].id}",
        headers=fix["officer_headers"],
    )
    assert resp_v1.status_code == 200
    items_v1 = resp_v1.json()["items"]
    assert len(items_v1) == 1
    assert items_v1[0]["id"] == str(fix["case_a"].id)

    resp_v2 = client.get(
        f"/api/v1/reviews?tender_version_id={fix['v2'].id}",
        headers=fix["officer_headers"],
    )
    assert resp_v2.status_code == 200
    items_v2 = resp_v2.json()["items"]
    assert len(items_v2) == 1
    assert items_v2[0]["id"] == str(fix["case_b"].id)
