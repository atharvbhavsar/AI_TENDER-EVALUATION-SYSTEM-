"""Add document_chunks table and pgvector extension for Phase 10 Hybrid Retrieval.

Revision ID: 0009_hybrid_retrieval_and_chunks
Revises: 0008_bidder_evidence_extraction
Create Date: 2026-09-18 03:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.db.types import TSVectorType, VectorType

# revision identifiers, used by Alembic.
revision: str = "0009_hybrid_retrieval_and_chunks"
down_revision: Union[str, None] = "0008_bidder_evidence_extraction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension and document_chunks table with indexes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Enable pgvector extension if PostgreSQL
    if is_postgres:
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except Exception:
            pass

    # 2. Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=True),
        sa.Column("bidder_id", sa.Uuid(), nullable=True),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("block_id", sa.String(length=100), nullable=True),
        sa.Column("table_reference", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False, server_default="TEXT"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("tsv_content", TSVectorType(), nullable=True),
        sa.Column("embedding", VectorType(1024), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default="BAAI/bge-m3"),
        sa.Column("embedding_model_version", sa.String(length=50), nullable=False, server_default="v1.0"),
        sa.Column("indexer_version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", "content_hash", "embedding_model", name="uq_document_chunk_identity"),
    )

    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_bid_submission_id"), "document_chunks", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_bidder_id"), "document_chunks", ["bidder_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_tender_version_id"), "document_chunks", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_tender_id"), "document_chunks", ["tender_id"], unique=False)
    op.create_index(op.f("ix_document_chunks_content_hash"), "document_chunks", ["content_hash"], unique=False)
    op.create_index(op.f("ix_document_chunks_created_at"), "document_chunks", ["created_at"], unique=False)
    op.create_index("ix_chunks_scope", "document_chunks", ["tender_id", "tender_version_id", "bidder_id", "bid_submission_id"], unique=False)
    op.create_index("ix_chunks_doc_idx", "document_chunks", ["document_id", "chunk_index"], unique=False)

    if is_postgres:
        # Full-Text Search GIN index
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_tsv ON document_chunks USING gin(tsv_content);")
        except Exception:
            pass
        # Vector index using HNSW (or IVFFlat)
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);")
        except Exception:
            pass



def downgrade() -> None:
    """Revert Phase 10 changes."""
    op.drop_index("ix_chunks_doc_idx", table_name="document_chunks")
    op.drop_index("ix_chunks_scope", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_created_at"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_content_hash"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_tender_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_tender_version_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_bidder_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_bid_submission_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
