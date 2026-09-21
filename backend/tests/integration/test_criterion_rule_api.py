"""Integration tests for Criterion Rule API endpoints and RBAC."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
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
def rule_api_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    auditor_role = db_session.query(Role).filter_by(name="AUDITOR").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_rule_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    auditor = User(
        id=uuid.uuid4(),
        email=f"auditor_rule_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Auditor User",
        is_active=True,
        password_hash="dummy_hash",
    )
    if auditor_role:
        auditor.roles.append(auditor_role)
    db_session.add(auditor)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-RULE-{uuid.uuid4().hex[:6]}",
        title="Tactical Drone Systems",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    approved_crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Annual Turnover Requirement",
        description="Minimum annual turnover of 50 Lakhs INR in last 3 financial years",
        source_clause="Clause 3.1: Minimum turnover of 50 Lakhs",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=5000000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add(approved_crit)

    unapproved_crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="TECH-001",
        name="OEM Authorization Certificate",
        description="Must submit valid OEM authorization certificate",
        source_clause="Clause 4.1: OEM authorization certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    db_session.add(unapproved_crit)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)
    auditor_token = create_access_token(subject=auditor.id)

    return {
        "officer": officer,
        "auditor": auditor,
        "officer_token": officer_token,
        "auditor_token": auditor_token,
        "tender": tender,
        "version": version,
        "approved_crit": approved_crit,
        "unapproved_crit": unapproved_crit,
    }


def test_auto_inferred_rule_creation_and_retrieval(client: TestClient, rule_api_fixture):
    """GET rule on approved criterion auto-infers rule if none exists."""
    token = rule_api_fixture["officer_token"]
    crit_id = rule_api_fixture["approved_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.get(f"/api/v1/criteria/{crit_id}/rule", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["criterion_id"] == str(crit_id)
    assert data["rule_type"] == "NUMERIC_THRESHOLD"
    assert data["configuration"]["threshold"] == 5000000.0


def test_explicit_rule_configuration_by_officer(client: TestClient, rule_api_fixture):
    """Officer can explicitly configure or override a rule on an approved criterion."""
    token = rule_api_fixture["officer_token"]
    crit_id = rule_api_fixture["approved_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "rule_type": "NUMERIC_THRESHOLD",
        "configuration": {
            "field": "amount",
            "operator": ">=",
            "threshold": 100000000.0,
            "unit": "INR",
        },
    }
    res = client.post(
        f"/api/v1/criteria/{crit_id}/rule",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["rule_type"] == "NUMERIC_THRESHOLD"
    assert data["configuration"]["threshold"] == 100000000.0
    assert data["status"] == "ACTIVE"


def test_rule_creation_rejected_on_unapproved_criterion(client: TestClient, rule_api_fixture):
    """Rule creation or retrieval fails on PENDING_REVIEW criterion."""
    token = rule_api_fixture["officer_token"]
    crit_id = rule_api_fixture["unapproved_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.get(f"/api/v1/criteria/{crit_id}/rule", headers=headers)
    assert res.status_code == 400
    assert "approved" in res.json()["detail"].lower()
