"""Document model, DocumentType enum, and ProcessingStatus enum."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.document_job import DocumentProcessingJob
    from app.db.models.processing_artifact import ProcessingArtifact
    from app.db.models.tender import Tender
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class DocumentType(str, enum.Enum):
    """Controlled document type categorization."""

    DIGITAL_PDF = "DIGITAL_PDF"
    SCANNED_PDF = "SCANNED_PDF"
    PHOTOGRAPH = "PHOTOGRAPH"
    WORD_DOCUMENT = "WORD_DOCUMENT"
    SPREADSHEET = "SPREADSHEET"
    UNKNOWN = "UNKNOWN"


class ProcessingStatus(str, enum.Enum):
    """Controlled document ingestion and processing lifecycle statuses."""

    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base):
    """Document entity storing procurement document metadata and storage references."""

    __tablename__ = "documents"

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
    bid_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    criterion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    file_extension: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    sha256_hash: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", native_enum=False),
        default=DocumentType.UNKNOWN,
        index=True,
        nullable=False,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status_enum", native_enum=False),
        default=ProcessingStatus.VALIDATED,
        index=True,
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
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

    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="documents",
    )
    tender_version: Mapped["TenderVersion"] = relationship(
        "TenderVersion",
        back_populates="documents",
    )
    submission: Mapped[Optional["BidSubmission"]] = relationship(
        "BidSubmission",
        back_populates="documents",
        lazy="selectin",
    )
    criterion: Mapped[Optional["TenderCriterion"]] = relationship(
        "TenderCriterion",
        lazy="selectin",
    )
    uploader: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    processing_jobs: Mapped[List["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentProcessingJob.created_at.desc()",
        lazy="selectin",
    )
    artifacts: Mapped[List["ProcessingArtifact"]] = relationship(
        "ProcessingArtifact",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ProcessingArtifact.created_at.asc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id='{self.id}', filename='{self.filename}', status='{self.processing_status}')>"
