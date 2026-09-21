"""Exhaustive tests for System Audit Logging in Phase 14."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.audit.service import AuditService
from app.auth.jwt import create_access_token
from app.db.models.audit_log import AuditLog
from app.db.models.role import Role
from app.db.models.tender import Tender, TenderStatus
from app.db.models.user import User


@pytest.fixture
def audit_fixture(db_session: Session):
    """Fixture providing officers and populated audit records."""
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"auditor_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Chief Auditor",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)
    db_session.flush()

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-AUDIT-{uuid.uuid4().hex[:6]}",
        title="Audited Procurement Process",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    # Create several distinct audit records
    a1 = AuditService.record(
        db_session,
        action="TENDER_CREATED",
        entity_type="TENDER",
        entity_id=str(tender.id),
        actor_id=officer.id,
        tender_id=tender.id,
        reason="Initial creation of tender",
    )
    a2 = AuditService.record(
        db_session,
        action="CRITERION_APPROVED",
        entity_type="CRITERION",
        entity_id=str(uuid.uuid4()),
        actor_id=officer.id,
        tender_id=tender.id,
        reason="Approved after board review",
    )
    a3 = AuditService.record(
        db_session,
        action="RULE_EVALUATED",
        entity_type="CRITERION_EVALUATION",
        entity_id=str(uuid.uuid4()),
        tender_id=tender.id,
        metadata_json={"result": "ELIGIBLE"},
    )
    db_session.commit()

    token = create_access_token(officer.id)
    headers = {"Authorization": f"Bearer {token}"}


    return {
        "officer": officer,
        "headers": headers,
        "tender": tender,
        "a1": a1,
        "a2": a2,
        "a3": a3,
    }


def test_audit_filtering_api(client: TestClient, audit_fixture):
    """Verify querying /api/v1/audit/logs with various filters."""
    headers = audit_fixture["headers"]
    tender = audit_fixture["tender"]
    officer = audit_fixture["officer"]

    # 1. Filter by tender_id
    res1 = client.get(f"/api/v1/audit/logs?tender_id={tender.id}", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 3

    # 2. Filter by action
    res2 = client.get(f"/api/v1/audit/logs?action=CRITERION_APPROVED", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 1
    assert data2["items"][0]["action"] == "CRITERION_APPROVED"

    # 3. Filter by actor_id
    res3 = client.get(f"/api/v1/audit/logs?actor_id={officer.id}", headers=headers)
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total"] == 2


def test_audit_immutability_no_update_or_delete_routes(client: TestClient, audit_fixture):
    """Verify there are no PUT/PATCH/DELETE endpoints to tamper with audit logs."""
    headers = audit_fixture["headers"]
    a1_id = audit_fixture["a1"].id

    assert client.delete(f"/api/v1/audit/logs/{a1_id}", headers=headers).status_code in [404, 405]
    assert client.put(f"/api/v1/audit/logs/{a1_id}", json={}, headers=headers).status_code in [404, 405]
    assert client.patch(f"/api/v1/audit/logs/{a1_id}", json={}, headers=headers).status_code in [404, 405]


def test_audit_rollback_on_failed_transaction(db_session: Session):
    """Verify that if an outer business transaction aborts, the audit record is also rolled back."""
    tender_id = uuid.uuid4()
    try:
        AuditService.record(
            db_session,
            action="TRANSACTION_TEST",
            entity_type="TENDER",
            entity_id=str(tender_id),
        )
        # Force a database failure
        raise ValueError("Simulated business error")
    except ValueError:
        db_session.rollback()

    # Query directly to ensure no phantom audit log exists
    entry = db_session.query(AuditLog).filter_by(action="TRANSACTION_TEST").first()
    assert entry is None
