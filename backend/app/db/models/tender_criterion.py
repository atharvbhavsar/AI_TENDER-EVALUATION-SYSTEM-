"""TenderCriterion model representing extracted eligibility criteria and officer approval lifecycle."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.criterion_approval_history import CriterionApprovalHistory
    from app.db.models.criterion_source_reference import CriterionSourceReference
    from app.db.models.extraction_run import ExtractionRun
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class CriterionCategory(str, enum.Enum):
    """Controlled procurement criterion taxonomy."""

    FINANCIAL = "FINANCIAL"
    TECHNICAL = "TECHNICAL"
    COMPLIANCE = "COMPLIANCE"
    CERTIFICATION = "CERTIFICATION"
    DOCUMENT_REQUIREMENT = "DOCUMENT_REQUIREMENT"


class RequirementType(str, enum.Enum):
    """Controlled requirement type classifications."""

    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"
    AMBIGUOUS = "AMBIGUOUS"


class ExtractionStatus(str, enum.Enum):
    """Controlled AI extraction confidence/support states."""

    EXTRACTED = "EXTRACTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class ApprovalStatus(str, enum.Enum):
    """Controlled officer review and approval lifecycle states."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TenderCriterion(Base):
    """Entity representing a structured candidate/approved eligibility criterion for a tender version."""

    __tablename__ = "tender_criteria"
    __table_args__ = (
        UniqueConstraint("tender_version_id", "criterion_code", name="uq_tender_version_criterion_code"),
        Index("ix_tender_criteria_version_category", "tender_version_id", "category"),
        Index("ix_tender_criteria_version_approval", "tender_version_id", "approval_status"),
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
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    criterion_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    # Working / Authoritative Values (updated on officer correction/approval)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    category: Mapped[CriterionCategory] = mapped_column(
        Enum(CriterionCategory, name="criterion_category_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    requirement_type: Mapped[RequirementType] = mapped_column(
        Enum(RequirementType, name="requirement_type_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    condition_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    operator: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    threshold_value: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    threshold_text: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    currency: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    period: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    mandatory: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    required_evidence: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    source_clause: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    source_page: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    source_section: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    source_block_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    source_table_reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # Extraction Metadata
    confidence: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status_enum", native_enum=False),
        default=ExtractionStatus.EXTRACTED,
        index=True,
        nullable=False,
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
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

    # Phase 8: Officer Review & Approval Lifecycle Fields
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum", native_enum=False),
        default=ApprovalStatus.PENDING_REVIEW,
        index=True,
        nullable=False,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    is_corrected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Original AI Extraction Snapshot (never overwritten by officer corrections)
    original_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    original_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    original_category: Mapped[Optional[CriterionCategory]] = mapped_column(
        Enum(CriterionCategory, name="criterion_category_enum", native_enum=False),
        nullable=True,
    )
    original_requirement_type: Mapped[Optional[RequirementType]] = mapped_column(
        Enum(RequirementType, name="requirement_type_enum", native_enum=False),
        nullable=True,
    )
    original_operator: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    original_threshold_value: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    original_threshold_text: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    original_unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    original_currency: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    original_period: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    original_mandatory: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    original_required_evidence: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    original_source_clause: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
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
        back_populates="criteria",
    )
    extraction_run: Mapped[Optional["ExtractionRun"]] = relationship(
        "ExtractionRun",
        back_populates="criteria",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="selectin",
    )
    source_references: Mapped[List["CriterionSourceReference"]] = relationship(
        "CriterionSourceReference",
        back_populates="criterion",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    approval_history: Mapped[List["CriterionApprovalHistory"]] = relationship(
        "CriterionApprovalHistory",
        back_populates="criterion",
        cascade="all, delete-orphan",
        order_by="CriterionApprovalHistory.created_at.asc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TenderCriterion(code='{self.criterion_code}', name='{self.name}', approval='{self.approval_status}')>"
