"""ReviewCase and related human decision models for Phase 13."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.criterion_evaluation import EvaluationResult

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.bidder import Bidder
    from app.db.models.bidder_evaluation import BidderEvaluation
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.evidence import Evidence
    from app.db.models.tender import Tender
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class ReviewStatus(str, enum.Enum):
    """Controlled lifecycle states for a human review case."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"


class ReviewPriority(str, enum.Enum):
    """Urgency level for review cases."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewIssueType(str, enum.Enum):
    """Controlled taxonomy of review issue triggers."""

    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    AMBIGUOUS_EVIDENCE = "AMBIGUOUS_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNREADABLE_EVIDENCE = "UNREADABLE_EVIDENCE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    UNSUPPORTED_RULE = "UNSUPPORTED_RULE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OFFICER_FLAGGED = "OFFICER_FLAGGED"
    OTHER = "OTHER"


class HumanDecision(str, enum.Enum):
    """Explicit human review decisions."""

    CONFIRM = "CONFIRM"
    OVERRIDE = "OVERRIDE"
    REQUEST_REVIEW = "REQUEST_REVIEW"


class ReviewCase(Base):
    """
    Review case tracking items requiring human officer inspection and decision.
    Tied strictly to tender version, bidder, submission, and criterion.
    """

    __tablename__ = "review_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenders.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    tender_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_versions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidders.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    bid_submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    criterion_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("criterion_evaluations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    overall_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidder_evaluations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    evaluation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), index=True, nullable=True
    )

    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status_enum", native_enum=False),
        default=ReviewStatus.OPEN,
        index=True,
        nullable=False,
    )
    priority: Mapped[ReviewPriority] = mapped_column(
        Enum(ReviewPriority, name="review_priority_enum", native_enum=False),
        default=ReviewPriority.MEDIUM,
        index=True,
        nullable=False,
    )
    issue_type: Mapped[ReviewIssueType] = mapped_column(
        Enum(ReviewIssueType, name="review_issue_type_enum", native_enum=False),
        default=ReviewIssueType.MANUAL_REVIEW_REQUIRED,
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender")
    tender_version: Mapped["TenderVersion"] = relationship("TenderVersion")
    bidder: Mapped["Bidder"] = relationship("Bidder")
    bid_submission: Mapped["BidSubmission"] = relationship("BidSubmission")
    criterion: Mapped[Optional["TenderCriterion"]] = relationship("TenderCriterion")
    criterion_evaluation: Mapped[Optional["CriterionEvaluation"]] = relationship("CriterionEvaluation")
    overall_evaluation: Mapped[Optional["BidderEvaluation"]] = relationship("BidderEvaluation")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    items: Mapped[List["ReviewItem"]] = relationship(
        "ReviewItem", back_populates="review_case", cascade="all, delete-orphan", lazy="selectin"
    )
    decisions: Mapped[List["OfficerDecision"]] = relationship(
        "OfficerDecision", back_populates="review_case", cascade="all, delete-orphan", lazy="selectin",
        order_by="OfficerDecision.created_at.desc()"
    )
    notes: Mapped[List["ReviewNote"]] = relationship(
        "ReviewNote", back_populates="review_case", cascade="all, delete-orphan", lazy="selectin",
        order_by="ReviewNote.created_at.asc()"
    )
    audit_logs: Mapped[List["ReviewAuditLog"]] = relationship(
        "ReviewAuditLog", back_populates="review_case", cascade="all, delete-orphan", lazy="selectin",
        order_by="ReviewAuditLog.created_at.asc()"
    )

    __table_args__ = (
        Index("ix_review_cases_scope", "tender_version_id", "bidder_id", "bid_submission_id"),
        Index("ix_review_cases_status_priority", "status", "priority"),
    )


class ReviewItem(Base):
    """Granular review item for specific criteria or evidence issues within a review case."""

    __tablename__ = "review_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="SET NULL"),
        nullable=True,
    )
    criterion_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("criterion_evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidder_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )

    issue_type: Mapped[ReviewIssueType] = mapped_column(
        Enum(ReviewIssueType, name="review_issue_type_enum", native_enum=False),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status_enum", native_enum=False),
        default=ReviewStatus.OPEN,
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    review_case: Mapped["ReviewCase"] = relationship("ReviewCase", back_populates="items")
    criterion: Mapped[Optional["TenderCriterion"]] = relationship("TenderCriterion")
    criterion_evaluation: Mapped[Optional["CriterionEvaluation"]] = relationship("CriterionEvaluation")
    evidence: Mapped[Optional["Evidence"]] = relationship("Evidence")


class OfficerDecision(Base):
    """
    Immutable record of an authorized officer's explicit review decision.
    Preserves original automated result and officer's decision + justification.
    """

    __tablename__ = "officer_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="SET NULL"),
        nullable=True,
    )
    criterion_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("criterion_evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )

    decision: Mapped[HumanDecision] = mapped_column(
        Enum(HumanDecision, name="human_decision_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    system_result: Mapped[EvaluationResult] = mapped_column(
        Enum(EvaluationResult, name="evaluation_result_enum", native_enum=False),
        nullable=False,
    )
    final_verdict: Mapped[Optional[EvaluationResult]] = mapped_column(
        Enum(EvaluationResult, name="evaluation_result_enum", native_enum=False),
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    officer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    review_case: Mapped["ReviewCase"] = relationship("ReviewCase", back_populates="decisions")
    officer: Mapped["User"] = relationship("User")


class ReviewNote(Base):
    """Immutable structured review note added by an authorized reviewer/officer."""

    __tablename__ = "review_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review_case: Mapped["ReviewCase"] = relationship("ReviewCase", back_populates="notes")
    author: Mapped["User"] = relationship("User")


class ReviewAuditLog(Base):
    """Audit log tracking every action and lifecycle event in human review."""

    __tablename__ = "review_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    review_case: Mapped["ReviewCase"] = relationship("ReviewCase", back_populates="audit_logs")
    actor: Mapped[Optional["User"]] = relationship("User")
