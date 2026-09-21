"""CriterionSourceReference model preserving audit trace to exact document blocks."""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
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
    from app.db.models.document import Document
    from app.db.models.tender_criterion import TenderCriterion


class CriterionSourceReference(Base):
    """Entity capturing exact source attribution (pages, blocks, tables, bboxes) for a criterion."""

    __tablename__ = "criterion_source_references"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_criteria.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    section: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    block_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    table_reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    source_text: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    criterion: Mapped["TenderCriterion"] = relationship(
        "TenderCriterion",
        back_populates="source_references",
    )
    document: Mapped["Document"] = relationship(
        "Document",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<CriterionSourceReference(criterion_id='{self.criterion_id}', page={self.page_number})>"
