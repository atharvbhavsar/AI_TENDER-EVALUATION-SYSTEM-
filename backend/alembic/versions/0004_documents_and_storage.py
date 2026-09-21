"""Create documents table.

Revision ID: 0004_documents_and_storage
Revises: 0003_tenders_and_versions
Create Date: 2026-09-18 02:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_documents_and_storage"
down_revision: Union[str, None] = "0003_tenders_and_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table and indexes."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_extension", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("document_type", sa.String(length=50), server_default="UNKNOWN", nullable=False),
        sa.Column("processing_status", sa.String(length=50), server_default="VALIDATED", nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_tender_id"), "documents", ["tender_id"], unique=False)
    op.create_index(op.f("ix_documents_tender_version_id"), "documents", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_documents_sha256_hash"), "documents", ["sha256_hash"], unique=False)
    op.create_index(op.f("ix_documents_uploaded_by"), "documents", ["uploaded_by"], unique=False)
    op.create_index(op.f("ix_documents_document_type"), "documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_documents_processing_status"), "documents", ["processing_status"], unique=False)
    op.create_index(op.f("ix_documents_created_at"), "documents", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop documents table and indexes."""
    op.drop_index(op.f("ix_documents_created_at"), table_name="documents")
    op.drop_index(op.f("ix_documents_processing_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_document_type"), table_name="documents")
    op.drop_index(op.f("ix_documents_uploaded_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_sha256_hash"), table_name="documents")
    op.drop_index(op.f("ix_documents_tender_version_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_tender_id"), table_name="documents")
    op.drop_table("documents")
