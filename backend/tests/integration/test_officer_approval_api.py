"""Integration tests for Officer Approval API endpoints and RBAC."""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.service import create_user
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User


@pytest.fixture
def procurement_token(db_session: Session) -> str:
    user = create_user(
        db=db_session,
        email="api_officer_approval@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Procurement Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )
    return create_access_token(subject=user.id)


@pytest.fixture
def reviewer_token(db_session: Session) -> str:
    user = create_user(
        db=db_session,
        email="api_reviewer_approval@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Technical Reviewer",
        role_names=["REVIEWER"],
    )
    return create_access_token(subject=user.id)


@pytest.fixture
def test_data(db_session: Session):
    admin = create_user(
        db=db_session,
        email="admin_app_api@crpf.gov.in",
        password="SecureAdminPassword123!",
        full_name="Admin Setup",
        role_names=["ADMIN"],
    )

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-API-APP-{uuid.uuid4().hex[:6].upper()}",
        title="Night Vision Goggles Procurement",
        description="Gen 3 NVG procurement for tactical operations.",
        status=TenderStatus.DRAFT,
        created_by=admin.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=admin.id,
    )
    db_session.add(version)
    db_session.flush()

    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="TECH-001",
        name="NVG Optical Resolution",
        description="Minimum optical resolution 64 lp/mm required.",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=64.0,
        threshold_text="64 lp/mm",
        unit="lp/mm",
        mandatory=True,
        source_clause="The NVG must have minimum 64 lp/mm optical resolution.",
        source_page=3,
        confidence=0.92,
        extraction_status=ExtractionStatus.EXTRACTED,
        model_name="mock-extractor-v1",
        model_version="1.0.0",
        prompt_version="v1",
        approval_status=ApprovalStatus.PENDING_REVIEW,
        is_corrected=False,
        original_name="NVG Optical Resolution",
        original_description="Minimum optical resolution 64 lp/mm required.",
        original_category=CriterionCategory.TECHNICAL,
        original_requirement_type=RequirementType.MANDATORY,
        original_operator=">=",
        original_threshold_value=64.0,
        original_threshold_text="64 lp/mm",
        original_source_clause="The NVG must have minimum 64 lp/mm optical resolution.",
    )
    db_session.add(crit)
    db_session.commit()

    return tender, version, crit


def test_officer_correction_endpoint(
    client: TestClient,
    procurement_token: str,
    test_data,
):
    """Test PATCH /tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}."""
    tender, version, crit = test_data

    payload = {
        "name": "Corrected NVG Resolution Specification",
        "threshold_value": 72.0,
        "threshold_text": "72 lp/mm",
        "reason": "Updated specification per technical committee recommendations",
    }

    response = client.patch(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}",
        json=payload,
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Corrected NVG Resolution Specification"
    assert data["threshold_value"] == 72.0
    assert data["is_corrected"] is True
    assert data["approval_status"] == "PENDING_REVIEW"
    assert data["original_threshold_value"] == 64.0  # Original AI snapshot intact!


def test_officer_approve_endpoint(
    client: TestClient,
    procurement_token: str,
    test_data,
):
    """Test POST /tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}/approve."""
    tender, version, crit = test_data

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/approve",
        json={"reason": "Approved by Officer in Charge"},
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "APPROVED"
    assert data["approved_at"] is not None
    assert data["approved_by"] is not None


def test_officer_reject_endpoint(
    client: TestClient,
    procurement_token: str,
    test_data,
):
    """Test POST /tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}/reject."""
    tender, version, crit = test_data

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/reject",
        json={"reason": "Duplicate requirement not applicable to Category B bidders"},
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "REJECTED"
    assert data["rejection_reason"] == "Duplicate requirement not applicable to Category B bidders"


def test_reject_without_reason_rejected_with_422(
    client: TestClient,
    procurement_token: str,
    test_data,
):
    """Test rejecting without reason fails validation with 422."""
    tender, version, crit = test_data

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/reject",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {procurement_token}"},
    )
    assert response.status_code == 422


def test_reviewer_forbidden_on_approval_endpoints(
    client: TestClient,
    reviewer_token: str,
    test_data,
):
    """Test RBAC: Reviewer lacks TENDER_APPROVE permission and is rejected with 403 on approve/reject/patch."""
    tender, version, crit = test_data

    # Approve attempt -> 403
    resp1 = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/approve",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp1.status_code == 403

    # Reject attempt -> 403
    resp2 = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/reject",
        json={"reason": "Test"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp2.status_code == 403

    # Patch attempt -> 403
    resp3 = client.patch(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp3.status_code == 403


def test_get_approval_history_endpoint(
    client: TestClient,
    procurement_token: str,
    reviewer_token: str,
    test_data,
):
    """Test GET /tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}/history."""
    tender, version, crit = test_data

    # 1. Correct
    client.patch(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}",
        json={"name": "History Spec", "threshold_value": 70.0, "reason": "Adjusted threshold"},
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    # 2. Approve
    client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/approve",
        json={"reason": "Approved"},
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    # Reviewer can view history (TENDER_READ)
    history_resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit.id}/history",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert history_resp.status_code == 200
    hist = history_resp.json()
    assert len(hist) == 2
    assert hist[0]["action"] == "CORRECT"
    assert hist[1]["action"] == "APPROVE"


def test_approval_mismatched_version_returns_404(
    client: TestClient,
    procurement_token: str,
    test_data,
):
    """Test attempting to approve a criterion against the wrong tender version returns 404."""
    tender, version, crit = test_data
    bogus_version_id = uuid.uuid4()

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{bogus_version_id}/criteria/{crit.id}/approve",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )
    assert response.status_code == 404
