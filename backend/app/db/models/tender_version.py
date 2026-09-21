"""TenderVersion model for historical and active tender versions."""

import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.document import Document
    from app.db.models.extraction_run import ExtractionRun
    from app.db.models.tender import Tender
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.user import User


class TenderVersion(Base):
    """TenderVersion entity representing a distinct historical state of a tender."""

    __tablename__ = "tender_versions"
    __table_args__ = (
        UniqueConstraint("tender_id", "version_number", name="uq_tender_version_number"),
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
    version_number: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False
    )
    version_label: Mapped[str] = mapped_column(
        String(100), default="Initial Release", nullable=False
    )
    effective_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="versions",
    )
    creator: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="tender_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    extraction_runs: Mapped[List["ExtractionRun"]] = relationship(
        "ExtractionRun",
        back_populates="tender_version",
        cascade="all, delete-orphan",
        order_by="ExtractionRun.created_at.desc()",
        lazy="selectin",
    )
    criteria: Mapped[List["TenderCriterion"]] = relationship(
        "TenderCriterion",
        back_populates="tender_version",
        cascade="all, delete-orphan",
        order_by="TenderCriterion.criterion_code.asc()",
        lazy="selectin",
    )
    submissions: Mapped[List["BidSubmission"]] = relationship(
        "BidSubmission",
        back_populates="tender_version",
        cascade="all, delete-orphan",
        order_by="BidSubmission.created_at.desc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TenderVersion(tender_id='{self.tender_id}', version={self.version_number}, is_active={self.is_active})>"
