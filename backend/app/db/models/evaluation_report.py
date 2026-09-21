"""EvaluationReport model for formal procurement reports."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
    from app.db.models.bidder import Bidder
    from app.db.models.bidder_evaluation import BidderEvaluation
    from app.db.models.tender import Tender
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class ReportType(str, enum.Enum):
    """Controlled taxonomy of formal evaluation reports."""

    BIDDER_EVALUATION_REPORT = "BIDDER_EVALUATION_REPORT"
    CONSOLIDATED_TENDER_REPORT = "CONSOLIDATED_TENDER_REPORT"


class ReportStatus(str, enum.Enum):
    """Lifecycle status of a report generation task."""

    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvaluationReport(Base):
    """
    Formal evaluation report artifact.
    Preserves report metadata, object storage location, SHA-256 integrity hash,
    and exact provenance linkage to tender versions, submissions, and evaluation runs.
    """

    __tablename__ = "evaluation_reports"

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
    bidder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidders.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    bid_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    evaluation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), index=True, nullable=True
    )
    overall_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidder_evaluations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum", native_enum=False),
        default=ReportStatus.GENERATING,
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=False)

    generated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    generation_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender")
    tender_version: Mapped["TenderVersion"] = relationship("TenderVersion")
    bidder: Mapped[Optional["Bidder"]] = relationship("Bidder")
    bid_submission: Mapped[Optional["BidSubmission"]] = relationship("BidSubmission")
    overall_evaluation: Mapped[Optional["BidderEvaluation"]] = relationship("BidderEvaluation")
    generator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[generated_by])

    __table_args__ = (
        Index("ix_eval_reports_scope", "tender_version_id", "bidder_id", "bid_submission_id"),
        Index("ix_eval_reports_type_status", "report_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<EvaluationReport(id='{self.id}', type='{self.report_type}', version={self.report_version}, status='{self.status}')>"
