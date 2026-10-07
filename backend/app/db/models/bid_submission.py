"""BidSubmission model representing a bidder's document submission for a specific tender version."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bidder import Bidder
    from app.db.models.document import Document
    from app.db.models.evidence import Evidence
    from app.db.models.evidence_extraction_run import EvidenceExtractionRun
    from app.db.models.tender_version import TenderVersion


class SubmissionStatus(str, enum.Enum):
    """Controlled lifecycle statuses for a bidder submission."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    REVIEW = "REVIEW"


class BidSubmission(Base):
    """BidSubmission entity capturing a bidder's response against a specific TenderVersion."""

    __tablename__ = "bid_submissions"
    __table_args__ = (
        UniqueConstraint(
            "tender_version_id", "bidder_id", "submission_reference",
            name="uq_submission_version_bidder_ref"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    submission_reference: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status_enum", native_enum=False),
        default=SubmissionStatus.DRAFT,
        index=True,
        nullable=False,
    )
    bidder_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commercial_quote: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    declaration_signed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tender_version: Mapped["TenderVersion"] = relationship(
        "TenderVersion",
        back_populates="submissions",
    )
    bidder: Mapped["Bidder"] = relationship(
        "Bidder",
        back_populates="submissions",
        lazy="selectin",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence_runs: Mapped[List["EvidenceExtractionRun"]] = relationship(
        "EvidenceExtractionRun",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="EvidenceExtractionRun.created_at.desc()",
        lazy="selectin",
    )
    evidence_items: Mapped[List["Evidence"]] = relationship(
        "Evidence",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="Evidence.created_at.asc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BidSubmission(ref='{self.submission_reference}', status='{self.status}')>"
