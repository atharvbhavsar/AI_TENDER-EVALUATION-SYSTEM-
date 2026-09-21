"""CriterionRule entity representing deterministic evaluation policies associated with approved criteria."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.tender_criterion import TenderCriterion
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User


class RuleType(str, enum.Enum):
    """Supported deterministic evaluation rule templates."""

    NUMERIC_THRESHOLD = "NUMERIC_THRESHOLD"
    EXPERIENCE_COUNT = "EXPERIENCE_COUNT"
    DATE_VALIDITY = "DATE_VALIDITY"
    CERTIFICATE_EXISTENCE = "CERTIFICATE_EXISTENCE"
    REGISTRATION_VALIDITY = "REGISTRATION_VALIDITY"
    BOOLEAN_COMPLIANCE = "BOOLEAN_COMPLIANCE"
    DATE_RANGE = "DATE_RANGE"
    CONDITIONAL_RULE = "CONDITIONAL_RULE"
    UNSUPPORTED = "UNSUPPORTED"


class RuleStatus(str, enum.Enum):
    """Lifecycle state of an evaluation rule."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    UNSUPPORTED = "UNSUPPORTED"


class CriterionRule(Base):
    """
    Deterministic rule configuration linked to an approved tender criterion.
    Defines the exact parameters passed to OPA/Rego policies for decision-making.
    """

    __tablename__ = "criterion_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tender_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType, name="rule_type_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    rule_version: Mapped[str] = mapped_column(
        String(50), default="v1.0", nullable=False
    )
    template_version: Mapped[str] = mapped_column(
        String(50), default="v1.0", nullable=False
    )
    rego_policy_reference: Mapped[str] = mapped_column(
        String(100), default="crpf.evaluation.main", nullable=False
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[RuleStatus] = mapped_column(
        Enum(RuleStatus, name="rule_status_enum", native_enum=False),
        default=RuleStatus.ACTIVE,
        index=True,
        nullable=False,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    # Relationships
    criterion: Mapped["TenderCriterion"] = relationship("TenderCriterion")
    tender_version: Mapped["TenderVersion"] = relationship("TenderVersion")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    evaluations: Mapped[list["CriterionEvaluation"]] = relationship(
        "CriterionEvaluation", back_populates="rule", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_criterion_rules_version_type", "tender_version_id", "rule_type"),
    )

    def __repr__(self) -> str:
        return f"<CriterionRule(id='{self.id}', crit_id='{self.criterion_id}', type='{self.rule_type}', status='{self.status}')>"
