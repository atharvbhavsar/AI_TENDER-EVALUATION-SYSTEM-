"""Unit tests for AuditService in Phase 14."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.audit.schemas import AuditLogFilter
from app.audit.service import AuditService
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.user import User


@pytest.fixture
def db_session():
    """In-memory SQLite session fixture for unit testing audit service."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_audit_service_record_and_query(db_session: Session):
    """Verify recording an append-only audit record and querying it with filters."""
    tender_id = uuid.uuid4()
    version_id = uuid.uuid4()
    submission_id = uuid.uuid4()

    entry = AuditService.record(
        db_session,
        action="TENDER_CREATED",
        entity_type="TENDER",
        entity_id=str(tender_id),
        tender_id=tender_id,
        tender_version_id=version_id,
        bid_submission_id=submission_id,
        reason="Initial tender created by officer",
        metadata_json={"stage": "DRAFT"},
    )
    db_session.commit()

    assert entry.id is not None
    assert entry.action == "TENDER_CREATED"

    # Query with filter
    logs, total = AuditService.query_logs(
        db_session,
        AuditLogFilter(tender_id=tender_id, action="TENDER_CREATED"),
    )
    assert total == 1
    assert len(logs) == 1
    assert logs[0].entity_type == "TENDER"
    assert logs[0].metadata_json.get("stage") == "DRAFT"


def test_audit_service_submission_trail(db_session: Session):
    """Verify get_submission_audit_trail returns all events for a given submission."""
    sub_id = uuid.uuid4()
    other_sub_id = uuid.uuid4()

    # Add 2 events for sub_id, 1 for other_sub_id
    AuditService.record(
        db_session,
        action="EVIDENCE_EXTRACTED",
        entity_type="EVIDENCE",
        bid_submission_id=sub_id,
    )
    AuditService.record(
        db_session,
        action="RULE_EVALUATED",
        entity_type="CRITERION_EVALUATION",
        bid_submission_id=sub_id,
    )
    AuditService.record(
        db_session,
        action="EVIDENCE_EXTRACTED",
        entity_type="EVIDENCE",
        bid_submission_id=other_sub_id,
    )
    db_session.commit()

    logs, total = AuditService.get_submission_audit_trail(db_session, sub_id)
    assert total == 2
    assert len(logs) == 2
    actions = [l.action for l in logs]
    assert "EVIDENCE_EXTRACTED" in actions
    assert "RULE_EVALUATED" in actions
