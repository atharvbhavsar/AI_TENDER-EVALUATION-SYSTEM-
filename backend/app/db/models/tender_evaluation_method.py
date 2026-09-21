"""TenderEvaluationMethod model representing the tender's prescribed evaluation and ranking methodology."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.tender import Tender
    from app.db.models.tender_version import TenderVersion


class EvaluationMethodType(str, enum.Enum):
    """Supported tender evaluation methodologies."""

    L1 = "L1"
    QCBS = "QCBS"
    TECHNICAL_SCORE = "TECHNICAL_SCORE"
    WEIGHTED_TECHNICAL_FINANCIAL = "WEIGHTED_TECHNICAL_FINANCIAL"
    TENDER_DEFINED = "TENDER_DEFINED"


class RankingDirection(str, enum.Enum):
    """Direction of ranking (lowest first for L1, highest first for QCBS)."""

    ASCENDING = "ASCENDING"  # Lowest price/score is rank 1 (e.g., L1)
    DESCENDING = "DESCENDING"  # Highest score is rank 1 (e.g., QCBS / technical score)


class TenderEvaluationMethod(Base):
    """
    TenderEvaluationMethod entity capturing the tender-specified evaluation
    and ranking criteria (e.g. L1 lowest evaluated price, or QCBS 70/30).
    Tied directly to the immutable TenderVersion.
    """

    __tablename__ = "tender_evaluation_methods"
    __table_args__ = (
        UniqueConstraint("tender_version_id", "version", name="uq_tender_version_eval_method"),
        Index("ix_eval_method_tender_version", "tender_version_id"),
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
        nullable=False,
    )
    method_type: Mapped[EvaluationMethodType] = mapped_column(
        Enum(EvaluationMethodType, name="eval_method_type_enum", native_enum=False),
        default=EvaluationMethodType.L1,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    financial_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    minimum_technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ranking_direction: Mapped[RankingDirection] = mapped_column(
        Enum(RankingDirection, name="ranking_direction_enum", native_enum=False),
        default=RankingDirection.ASCENDING,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    tie_breaker_rule: Mapped[Optional[str]] = mapped_column(
        String(100), default="HUMAN_REVIEW", nullable=True
    )
    version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
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

    def __repr__(self) -> str:
        return (
            f"<TenderEvaluationMethod(id='{self.id}', "
            f"type='{self.method_type}', version='{self.version}')>"
        )
