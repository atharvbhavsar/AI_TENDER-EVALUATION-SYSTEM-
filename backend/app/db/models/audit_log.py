"""AuditLog entity for system-wide append-only audit tracking."""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.bidder import Bidder
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.document import Document
    from app.db.models.evidence import Evidence
    from app.db.models.review_case import ReviewCase
    from app.db.models.tender import Tender
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class AuditLog(Base):
    """
    Append-only system-wide audit log for all critical business and evaluation events.
    Preserves exact actor, entity references, previous/new states, document hashes,
    and structured metadata for complete traceability and government-grade provenance.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Actor information
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Action and Entity classification
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    # Scoping Foreign Keys
    tender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    tender_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_versions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    bidder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    bid_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidder_evidence.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("criterion_evaluations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_cases.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Document Integrity & Provenance
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # State capture
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Observability & Tracing
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    source_service: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])
    tender: Mapped[Optional["Tender"]] = relationship("Tender", foreign_keys=[tender_id])
    tender_version: Mapped[Optional["TenderVersion"]] = relationship("TenderVersion", foreign_keys=[tender_version_id])
    bidder: Mapped[Optional["Bidder"]] = relationship("Bidder", foreign_keys=[bidder_id])
    bid_submission: Mapped[Optional["BidSubmission"]] = relationship("BidSubmission", foreign_keys=[bid_submission_id])
    criterion: Mapped[Optional["TenderCriterion"]] = relationship("TenderCriterion", foreign_keys=[criterion_id])
    document: Mapped[Optional["Document"]] = relationship("Document", foreign_keys=[document_id])
    evidence: Mapped[Optional["Evidence"]] = relationship("Evidence", foreign_keys=[evidence_id])
    criterion_evaluation: Mapped[Optional["CriterionEvaluation"]] = relationship("CriterionEvaluation", foreign_keys=[evaluation_id])
    review_case: Mapped[Optional["ReviewCase"]] = relationship("ReviewCase", foreign_keys=[review_id])

    __table_args__ = (
        Index("ix_audit_logs_scope", "tender_id", "tender_version_id", "bidder_id", "bid_submission_id"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_action_ts", "action", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id='{self.id}', action='{self.action}', entity='{self.entity_type}:{self.entity_id}')>"


@event.listens_for(AuditLog, "before_update")
def receive_before_update(mapper, connection, target):
    """Enforce append-only immutability for AuditLog instances."""
    raise ValueError("AuditLog records are strictly append-only and cannot be updated.")


@event.listens_for(AuditLog, "before_delete")
def receive_before_delete(mapper, connection, target):
    """Enforce append-only immutability for AuditLog instances."""
    raise ValueError("AuditLog records are strictly append-only and cannot be deleted.")
