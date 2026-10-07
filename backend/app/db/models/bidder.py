"""Bidder domain model representing procurement participants."""

import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.tender import Tender


class Bidder(Base):
    """Bidder entity representing a legal company or entity participating in a tender."""

    __tablename__ = "bidders"
    __table_args__ = (
        UniqueConstraint("tender_id", "bidder_code", name="uq_tender_bidder_code"),
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
    bidder_code: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )
    legal_name: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="bidders",
    )
    submissions: Mapped[List["BidSubmission"]] = relationship(
        "BidSubmission",
        back_populates="bidder",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Bidder(code='{self.bidder_code}', name='{self.legal_name}')>"
