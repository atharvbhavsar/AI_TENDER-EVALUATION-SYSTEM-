"""EvidenceExtractionRun model tracking AI evidence extraction executions on bidder submissions."""

import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.extraction_run import ExtractionRunStatus

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.evidence import Evidence
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.user import User


class EvidenceExtractionRun(Base):
    """Entity tracking a single AI evidence extraction execution against a bidder submission."""

    __tablename__ = "evidence_extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bid_submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    extractor_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[ExtractionRunStatus] = mapped_column(
        Enum(ExtractionRunStatus, name="evidence_extraction_run_status_enum", native_enum=False),
        default=ExtractionRunStatus.QUEUED,
        index=True,
        nullable=False,
    )
    evidence_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
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

    submission: Mapped["BidSubmission"] = relationship(
        "BidSubmission",
        back_populates="evidence_runs",
    )
    criterion: Mapped[Optional["TenderCriterion"]] = relationship(
        "TenderCriterion",
        lazy="selectin",
    )
    creator: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    evidence_items: Mapped[List["Evidence"]] = relationship(
        "Evidence",
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<EvidenceExtractionRun(id='{self.id}', status='{self.status}', count={self.evidence_count})>"
