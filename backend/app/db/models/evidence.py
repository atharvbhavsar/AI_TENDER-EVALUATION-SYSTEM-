"""Evidence model and EvidenceStatus enum for bidder qualification validation."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.document import Document
    from app.db.models.evidence_extraction_run import EvidenceExtractionRun
    from app.db.models.tender_criterion import TenderCriterion


class EvidenceStatus(str, enum.Enum):
    """Controlled evidence extraction & validation statuses."""

    FOUND = "FOUND"
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    CONFLICTING = "CONFLICTING"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"


class Evidence(Base):
    """Evidence entity capturing extracted proof from bidder documents against an approved criterion."""

    __tablename__ = "bidder_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    bid_submission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_extraction_runs.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50), default="DOCUMENT", nullable=False
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    extracted_value: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    normalized_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    currency: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )
    period: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    date_value: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    certificate_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    experience_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    extracted_bidder_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, name="evidence_status_enum", native_enum=False),
        default=EvidenceStatus.FOUND,
        index=True,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    source_page: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    source_block_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    source_table_reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    bbox: Mapped[Optional[List[float]]] = mapped_column(
        JSON, nullable=True
    )
    raw_extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    validation_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    extractor_version: Mapped[str] = mapped_column(
        String(50), nullable=False
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

    criterion: Mapped["TenderCriterion"] = relationship(
        "TenderCriterion",
        lazy="selectin",
    )
    submission: Mapped["BidSubmission"] = relationship(
        "BidSubmission",
        back_populates="evidence_items",
    )
    document: Mapped[Optional["Document"]] = relationship(
        "Document",
        lazy="selectin",
    )
    extraction_run: Mapped["EvidenceExtractionRun"] = relationship(
        "EvidenceExtractionRun",
        back_populates="evidence_items",
    )

    def __repr__(self) -> str:
        return f"<Evidence(id='{self.id}', criterion_id='{self.criterion_id}', status='{self.status}')>"
