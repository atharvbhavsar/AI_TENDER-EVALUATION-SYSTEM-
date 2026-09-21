"""RetrievalChunk entity representing searchable units of processed documents with embeddings."""

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
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
from app.db.types import TSVectorType, VectorType

if TYPE_CHECKING:
    from app.db.models.bid_submission import BidSubmission
    from app.db.models.bidder import Bidder
    from app.db.models.document import Document
    from app.db.models.tender import Tender
    from app.db.models.tender_version import TenderVersion


class RetrievalChunk(Base):
    """
    Searchable document chunk retaining complete source traceability,
    lexical tsvector representation, and pgvector embeddings.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bid_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bid_submissions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    bidder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    tender_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    block_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    table_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="TEXT", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    bbox: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Lexical and Semantic representations
    tsv_content: Mapped[Optional[str]] = mapped_column(TSVectorType, nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType(1024), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100), default="BAAI/bge-m3", nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    indexer_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

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
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])
    bid_submission: Mapped[Optional["BidSubmission"]] = relationship("BidSubmission", foreign_keys=[bid_submission_id])
    bidder: Mapped[Optional["Bidder"]] = relationship("Bidder", foreign_keys=[bidder_id])
    tender_version: Mapped["TenderVersion"] = relationship("TenderVersion", foreign_keys=[tender_version_id])
    tender: Mapped["Tender"] = relationship("Tender", foreign_keys=[tender_id])

    __table_args__ = (
        Index("ix_chunks_scope", "tender_id", "tender_version_id", "bidder_id", "bid_submission_id"),
        Index("ix_chunks_doc_idx", "document_id", "chunk_index"),
        UniqueConstraint("document_id", "chunk_index", "content_hash", "embedding_model", name="uq_document_chunk_identity"),
    )

    def __repr__(self) -> str:
        return f"<RetrievalChunk(id='{self.id}', doc_id='{self.document_id}', idx={self.chunk_index}, page={self.page_number})>"
