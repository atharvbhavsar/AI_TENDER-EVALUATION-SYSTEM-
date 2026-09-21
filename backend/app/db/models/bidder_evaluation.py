"""BidderEvaluation entity representing aggregated overall eligibility outcomes."""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.criterion_evaluation import EvaluationResult

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.bidder import Bidder
    from app.db.models.tender import Tender
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class BidderEvaluation(Base):
    """
    Immutable overall bidder evaluation record produced by deterministic aggregation
    of criterion-level evaluation results.
    Preserves exact summary metrics, snapshots of evaluated criteria and rule versions,
    and structured deterministic explanations.
    """

    __tablename__ = "bidder_evaluations"

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
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )

    # Aggregated Result and Policy Version
    result: Mapped[EvaluationResult] = mapped_column(
        Enum(EvaluationResult, name="evaluation_result_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    aggregation_policy_version: Mapped[str] = mapped_column(
        String(50), default="v1.0", nullable=False
    )

    # Deterministic Summary Counts
    criterion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manual_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Mandatory Criteria Summary
    mandatory_criterion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_not_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_manual_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Optional Criteria Summary
    optional_criterion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    optional_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    optional_not_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    optional_manual_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Snapshots and Explanations
    rule_version_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    explanation: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    # Metadata & Provenance
    evaluated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender")
    tender_version: Mapped["TenderVersion"] = relationship("TenderVersion")
    bidder: Mapped["Bidder"] = relationship("Bidder")
    bid_submission: Mapped["BidSubmission"] = relationship("BidSubmission")
    evaluator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[evaluated_by])

    __table_args__ = (
        Index("ix_bidder_eval_submission", "bid_submission_id"),
        Index("ix_bidder_eval_scope", "tender_version_id", "bidder_id", "bid_submission_id"),
        Index("ix_bidder_eval_run", "evaluation_run_id"),
        Index("ix_bidder_eval_result", "result"),
    )

    def __repr__(self) -> str:
        return f"<BidderEvaluation(id='{self.id}', sub='{self.bid_submission_id}', result='{self.result}')>"
