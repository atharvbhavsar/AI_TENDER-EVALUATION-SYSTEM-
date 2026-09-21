"""CriterionApprovalHistory model for auditable officer review and approvals."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.tender_criterion import ApprovalStatus, TenderCriterion
    from app.db.models.user import User


class ApprovalAction(str, enum.Enum):
    """Controlled actions in the criterion approval workflow."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CORRECT = "CORRECT"


class CriterionApprovalHistory(Base):
    """Entity capturing every officer review action, correction diff, and status change."""

    __tablename__ = "criterion_approval_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action_enum", native_enum=False),
        index=True,
        nullable=False,
    )
    previous_status: Mapped[str] = mapped_column(
        String_or_Enum := Enum("PENDING_REVIEW", "APPROVED", "REJECTED", name="approval_status_enum", native_enum=False),
        nullable=False,
    )
    new_status: Mapped[str] = mapped_column(
        String_or_Enum,
        nullable=False,
    )
    changed_fields: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    officer_id: Mapped[uuid.UUID] = mapped_column(
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

    criterion: Mapped["TenderCriterion"] = relationship(
        "TenderCriterion",
        back_populates="approval_history",
    )
    officer: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<CriterionApprovalHistory(action='{self.action}', criterion='{self.criterion_id}', officer='{self.officer_id}')>"
