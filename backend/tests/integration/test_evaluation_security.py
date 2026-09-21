"""Integration tests for security, authorization, and RBAC in evaluation endpoints."""

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
def eval_security_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_sec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer_sec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Reviewer Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if reviewer_role:
        reviewer.roles.append(reviewer_role)
    db_session.add(reviewer)

    user_without_roles = User(
        id=uuid.uuid4(),
        email=f"unprivileged_{uuid.uuid4().hex[:6]}@external.com",
        full_name="Unprivileged User",
        is_active=True,
        password_hash="dummy_hash",
    )
    db_session.add(user_without_roles)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-SEC-{uuid.uuid4().hex[:6]}",
        title="Security Patrol Vehicles",
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

    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="TECH-SEC-01",
        name="Vehicle Emission Standard",
        description="Vehicle Emission Standard BS-VI requirement",
        source_clause="Clause 2.1: Vehicle Emission Standard",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add(crit)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)
    reviewer_token = create_access_token(subject=reviewer.id)
    unprivileged_token = create_access_token(subject=user_without_roles.id)

    return {
        "officer_token": officer_token,
        "reviewer_token": reviewer_token,
        "unprivileged_token": unprivileged_token,
        "tender": tender,
        "crit": crit,
    }


def test_unauthenticated_request_rejected(client: TestClient, eval_security_fixture):
    """Unauthenticated requests to evaluation endpoints must return 401."""
    crit_id = eval_security_fixture["crit"].id

    res = client.get(f"/api/v1/criteria/{crit_id}/rule")
    assert res.status_code == 401


def test_unprivileged_role_cannot_configure_rules(client: TestClient, eval_security_fixture):
    """Users without TENDER_UPDATE permission cannot configure rules."""
    token = eval_security_fixture["unprivileged_token"]
    crit_id = eval_security_fixture["crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/criteria/{crit_id}/rule",
        json={
            "rule_type": "NUMERIC_THRESHOLD",
            "configuration": {"threshold": 1.0},
        },
        headers=headers,
    )
    assert res.status_code == 403


def test_reviewer_can_read_rules_and_evaluations(client: TestClient, eval_security_fixture):
    """Reviewers with TENDER_READ / EVALUATION_READ can read rules and evaluations."""
    token = eval_security_fixture["reviewer_token"]
    crit_id = eval_security_fixture["crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.get(
        f"/api/v1/criteria/{crit_id}/rule",
        headers=headers,
    )
    assert res.status_code == 200
