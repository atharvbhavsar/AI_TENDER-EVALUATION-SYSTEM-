"""BidderRanking model representing auditable, deterministic comparative ranking results."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
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


class RankingStatus(str, enum.Enum):
    """Status of a bidder's inclusion or standing in the comparative ranking."""

    QUALIFIED_RANKED = "QUALIFIED_RANKED"  # Eligible and successfully assigned a rank
    EXCLUDED_INELIGIBLE = "EXCLUDED_INELIGIBLE"  # Excluded due to failed mandatory criteria
    PENDING_MANUAL_REVIEW = "PENDING_MANUAL_REVIEW"  # Held because human manual review is unresolved
    TIE_REQUIRES_HUMAN_REVIEW = "TIE_REQUIRES_HUMAN_REVIEW"  # Equal rank/score without defined tie-breaker
    MISSING_FINANCIAL_BID = "MISSING_FINANCIAL_BID"  # Eligible but missing price quotation
    DISQUALIFIED_TECHNICAL = "DISQUALIFIED_TECHNICAL"  # Failed minimum technical score threshold


class BidderRanking(Base):
    """
    Immutable comparative evaluation and ranking result record for a bidder submission.
    Produced deterministically by ComparativeEvaluationService with complete calculation
    breakdowns, evidence provenance, and tender version isolation.
    """

    __tablename__ = "bidder_rankings"
    __table_args__ = (
        Index("ix_bidder_rankings_scope", "tender_version_id", "evaluation_run_id"),
        Index("ix_bidder_rankings_bidder", "bidder_id"),
        Index("ix_bidder_rankings_rank", "tender_version_id", "rank"),
    )

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
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
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

    # Method & Eligibility snapshot
    evaluation_method: Mapped[str] = mapped_column(
        String(50), default="L1", nullable=False
    )
    eligibility_status: Mapped[EvaluationResult] = mapped_column(
        Enum(EvaluationResult, name="evaluation_result_enum", native_enum=False),
        nullable=False,
    )

    # Numeric & Score fields
    quoted_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    financial_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    combined_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Rank & Status
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rank_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ranking_status: Mapped[RankingStatus] = mapped_column(
        Enum(RankingStatus, name="ranking_status_enum", native_enum=False),
        default=RankingStatus.QUALIFIED_RANKED,
        nullable=False,
    )

    # Audit & Provenance details
    calculation_details: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    provenance_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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

    def __repr__(self) -> str:
        return (
            f"<BidderRanking(bidder_id='{self.bidder_id}', "
            f"rank={self.rank_label or self.rank}, status='{self.ranking_status}')>"
        )
