"""Integration tests for Bidder and Submission REST APIs and RBAC."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.role import Role
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User


@pytest.fixture
def test_setup_data(db_session):
    """Set up test tender, version, and officer/reviewer users."""
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer_user = User(
        id=uuid.uuid4(),
        email="officer_bid@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="hashed_dummy_password",
    )
    if officer_role:
        officer_user.roles.append(officer_role)
    db_session.add(officer_user)

    reviewer_user = User(
        id=uuid.uuid4(),
        email="reviewer_bid@crpf.gov.in",
        full_name="Compliance Reviewer",
        is_active=True,
        password_hash="hashed_dummy_password",
    )
    if reviewer_role:
        reviewer_user.roles.append(reviewer_role)
    db_session.add(reviewer_user)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-BID-TEST-{uuid.uuid4().hex[:6]}",
        title="Procurement of Drones",
        issuing_authority="CRPF Directorate",
        status=TenderStatus.PUBLISHED,
        created_by=officer_user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=officer_user.id,
    )
    db_session.add(version)
    db_session.commit()

    return {
        "officer": officer_user,
        "reviewer": reviewer_user,
        "tender": tender,
        "version": version,
    }


def test_bidder_crud_lifecycle_and_rbac(client: TestClient, test_setup_data):
    """Test creating and listing bidders under a tender."""
    tender_id = str(test_setup_data["tender"].id)
    officer_token = create_access_token(subject=test_setup_data["officer"].id)
    reviewer_token = create_access_token(subject=test_setup_data["reviewer"].id)

    # 1. Unauthenticated request rejected
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        json={"bidder_code": "BID-01", "legal_name": "Garuda Aerospace Pvt Ltd"},
    )
    assert resp.status_code == 401

    # 2. Reviewer cannot create bidder (requires TENDER_UPDATE)
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"bidder_code": "BID-01", "legal_name": "Garuda Aerospace Pvt Ltd"},
    )
    assert resp.status_code == 403

    # 3. Officer creates bidder successfully
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={
            "bidder_code": "BID-01",
            "legal_name": "Garuda Aerospace Pvt Ltd",
            "contact_email": "tenders@garuda.in",
            "contact_phone": "+91-9988776655",
        },
    )
    assert resp.status_code == 201
    bidder_data = resp.json()
    assert bidder_data["bidder_code"] == "BID-01"
    bidder_id = bidder_data["id"]

    # 4. Duplicate bidder_code rejected with 409
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"bidder_code": "BID-01", "legal_name": "Duplicate Garuda"},
    )
    assert resp.status_code == 409

    # 5. List bidders
    resp = client.get(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    list_data = resp.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["id"] == bidder_id


def test_submission_lifecycle(client: TestClient, test_setup_data):
    """Test creating and listing submissions scoped to a tender version."""
    tender_id = str(test_setup_data["tender"].id)
    version_id = str(test_setup_data["version"].id)
    officer_token = create_access_token(subject=test_setup_data["officer"].id)

    # 1. Register bidder first
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"bidder_code": "BID-SUB-01", "legal_name": "Zen Technologies Limited"},
    )
    assert resp.status_code == 201
    bidder_id = resp.json()["id"]

    # 2. Create submission
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"submission_reference": "ZEN-SUB-2026-001"},
    )
    assert resp.status_code == 201
    sub_data = resp.json()
    assert sub_data["submission_reference"] == "ZEN-SUB-2026-001"
    assert sub_data["status"] == "RECEIVED"
    sub_id = sub_data["id"]

    # 3. List submissions
    resp = client.get(
        f"/api/v1/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == sub_id
