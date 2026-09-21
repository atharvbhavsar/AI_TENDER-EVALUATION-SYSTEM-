"""DocumentProcessingJob model and JobStatus enum."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.document import Document


class JobStatus(str, enum.Enum):
    """Controlled document processing job execution statuses."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


class JobType(str, enum.Enum):
    """Supported asynchronous processing job types."""

    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    OCR_PROCESSING = "OCR_PROCESSING"
    EVIDENCE_EXTRACTION = "EVIDENCE_EXTRACTION"
    EMBEDDING_GENERATION = "EMBEDDING_GENERATION"


class DocumentProcessingJob(Base):
    """Document processing job entity for asynchronous execution and retry tracking."""

    __tablename__ = "document_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(50),
        default=JobType.DOCUMENT_PROCESSING.value,
        index=True,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum", native_enum=False),
        default=JobStatus.QUEUED,
        index=True,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    processor_version: Mapped[str] = mapped_column(
        String(50), default="1.0.0", nullable=False
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

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="processing_jobs",
    )

    @property
    def processing_version(self) -> str:
        return self.processor_version

    @processing_version.setter
    def processing_version(self, value: str) -> None:
        self.processor_version = value

    def __repr__(self) -> str:
        return f"<DocumentProcessingJob(id='{self.id}', document_id='{self.document_id}', job_type='{self.job_type}', status='{self.status}')>"
