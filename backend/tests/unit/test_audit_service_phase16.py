"""Unit tests for Phase 16 AuditService and Audit Log Immutability."""

import datetime
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit.events import AuditAction
from app.audit.schemas import AuditLogFilter
from app.audit.service import AuditService
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.user import User


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session fixture for unit testing audit service."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_audit_service_record_with_all_phase16_fields(db_session: Session):
    """Verify recording an audit record with Phase 16 evidence, evaluation, and review scoping."""
    tender_id = uuid.uuid4()
    version_id = uuid.uuid4()
    bidder_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    crit_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    ev_id = uuid.uuid4()
    eval_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    entry = AuditService.record(
        db_session,
        action=AuditAction.CRITERION_EVALUATED.value,
        entity_type="CRITERION_EVALUATION",
        entity_id=str(eval_id),
        actor_id=actor_id,
        actor_role="EVALUATION_OFFICER",
        tender_id=tender_id,
        tender_version_id=version_id,
        bidder_id=bidder_id,
        bid_submission_id=sub_id,
        criterion_id=crit_id,
        document_id=doc_id,
        evidence_id=ev_id,
        evaluation_id=eval_id,
        review_id=rev_id,
        document_hash="a" * 64,
        previous_state={"result": "PENDING"},
        new_state={"result": "ELIGIBLE"},
        reason="Deterministic rule match",
        correlation_id="req-12345",
        source_service="rule_engine",
        metadata_json={"rule_version": "1.0.0"},
    )
    db_session.commit()

    assert entry.id is not None
    assert entry.action == "CRITERION_EVALUATED"
    assert entry.evidence_id == ev_id
    assert entry.evaluation_id == eval_id
    assert entry.review_id == rev_id
    assert entry.document_hash == "a" * 64
    assert entry.metadata_json == {"rule_version": "1.0.0"}
    assert isinstance(entry.timestamp, datetime.datetime)


def test_audit_service_query_filtering_phase16(db_session: Session):
    """Verify querying logs using Phase 16 filters."""
    ev_id1 = uuid.uuid4()
    ev_id2 = uuid.uuid4()
    sub_id = uuid.uuid4()

    AuditService.record(
        db_session,
        action=AuditAction.EVIDENCE_EXTRACTED.value,
        entity_type="EVIDENCE",
        entity_id=str(ev_id1),
        bid_submission_id=sub_id,
        evidence_id=ev_id1,
    )
    AuditService.record(
        db_session,
        action=AuditAction.EVIDENCE_VALIDATED.value,
        entity_type="EVIDENCE",
        entity_id=str(ev_id2),
        bid_submission_id=sub_id,
        evidence_id=ev_id2,
    )
    db_session.commit()

    # Query for ev_id1
    items, total = AuditService.query_logs(db_session, AuditLogFilter(evidence_id=ev_id1))
    assert total == 1
    assert items[0].evidence_id == ev_id1
    assert items[0].action == "EVIDENCE_EXTRACTED"

    # Query for ev_id2
    items, total = AuditService.query_logs(db_session, AuditLogFilter(evidence_id=ev_id2))
    assert total == 1
    assert items[0].evidence_id == ev_id2
    assert items[0].action == "EVIDENCE_VALIDATED"


def test_audit_immutability_before_update_listener(db_session: Session):
    """Verify that attempting to update an AuditLog entity raises ValueError."""
    entry = AuditService.record(
        db_session,
        action=AuditAction.TENDER_CREATED.value,
        entity_type="TENDER",
        entity_id="tender-1",
    )
    db_session.commit()

    # Attempt modification
    entry.action = "TENDER_MODIFIED_ILLEGALLY"
    with pytest.raises(ValueError, match="AuditLog records are strictly append-only and cannot be updated."):
        db_session.commit()


def test_audit_immutability_before_delete_listener(db_session: Session):
    """Verify that attempting to delete an AuditLog entity raises ValueError."""
    entry = AuditService.record(
        db_session,
        action=AuditAction.TENDER_CREATED.value,
        entity_type="TENDER",
        entity_id="tender-2",
    )
    db_session.commit()

    # Attempt deletion
    db_session.delete(entry)
    with pytest.raises(ValueError, match="AuditLog records are strictly append-only and cannot be deleted."):
        db_session.commit()


def test_audit_transactional_rollback(db_session: Session):
    """Verify that when a transaction rolls back, uncommitted audit records are not persisted."""
    tender_id = uuid.uuid4()
    AuditService.record(
        db_session,
        action=AuditAction.TENDER_CREATED.value,
        entity_type="TENDER",
        entity_id=str(tender_id),
        tender_id=tender_id,
    )
    # Rollback transaction
    db_session.rollback()

    items, total = AuditService.query_logs(db_session, AuditLogFilter(tender_id=tender_id))
    assert total == 0
    assert len(items) == 0
