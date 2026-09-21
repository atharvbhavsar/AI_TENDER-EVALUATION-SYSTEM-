"""ProcessingArtifact model and ArtifactType enum."""

import datetime
import enum
import uuid
from typing import TYPE_CHECKING
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
    from app.db.models.document import Document


class ArtifactType(str, enum.Enum):
    """Types of generated document processing artifacts."""

    NORMALIZED_CONTENT = "NORMALIZED_CONTENT"
    EXTRACTED_TEXT = "EXTRACTED_TEXT"
    LAYOUT_METADATA = "LAYOUT_METADATA"
    PAGE_IMAGE = "PAGE_IMAGE"


class ProcessingArtifact(Base):
    """ProcessingArtifact entity storing metadata references for generated processing output."""

    __tablename__ = "processing_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, name="artifact_type_enum", native_enum=False),
        default=ArtifactType.NORMALIZED_CONTENT,
        index=True,
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    mime_type: Mapped[str] = mapped_column(
        String(100), default="application/json", nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="artifacts",
    )

    def __repr__(self) -> str:
        return f"<ProcessingArtifact(id='{self.id}', document_id='{self.document_id}', type='{self.artifact_type}')>"
