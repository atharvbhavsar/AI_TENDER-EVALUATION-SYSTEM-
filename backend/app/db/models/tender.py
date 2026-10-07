"""Tender model and lifecycle status enum."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bidder import Bidder
    from app.db.models.document import Document
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class TenderStatus(str, enum.Enum):
    """Controlled tender lifecycle statuses."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Tender(Base):
    """Tender procurement record entity."""

    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tender_number: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issuing_authority: Mapped[str] = mapped_column(
        String(255), default="Central Reserve Police Force", nullable=False
    )
    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, name="tender_status_enum", native_enum=False),
        default=TenderStatus.DRAFT,
        index=True,
        nullable=False,
    )
    submission_deadline: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
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

    creator: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    versions: Mapped[List["TenderVersion"]] = relationship(
        "TenderVersion",
        back_populates="tender",
        order_by="TenderVersion.version_number",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="tender",
        cascade="all, delete-orphan",
    )
    bidders: Mapped[List["Bidder"]] = relationship(
        "Bidder",
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="Bidder.created_at.asc()",
        lazy="selectin",
    )

    @property
    def active_version(self) -> Optional["TenderVersion"]:
        """Return the currently effective active version of the tender."""
        for version in self.versions:
            if version.is_active:
                return version
        return None

    def __repr__(self) -> str:
        return f"<Tender(tender_number='{self.tender_number}', status='{self.status}')>"
