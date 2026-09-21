"""ExtractionRun model tracking AI criterion extraction jobs and versioning."""

import datetime
import enum
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

if TYPE_CHECKING:
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class ExtractionRunStatus(str, enum.Enum):
    """Lifecycle statuses for an AI extraction run."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ExtractionRun(Base):
    """Entity tracking a single AI extraction execution run against a tender version."""

    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tender_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_versions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
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
        Enum(ExtractionRunStatus, name="extraction_run_status_enum", native_enum=False),
        default=ExtractionRunStatus.QUEUED,
        index=True,
        nullable=False,
    )
    criteria_count: Mapped[int] = mapped_column(
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

    tender_version: Mapped["TenderVersion"] = relationship(
        "TenderVersion",
        back_populates="extraction_runs",
    )
    creator: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    criteria: Mapped[List["TenderCriterion"]] = relationship(
        "TenderCriterion",
        back_populates="extraction_run",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ExtractionRun(id='{self.id}', status='{self.status}', criteria={self.criteria_count})>"
