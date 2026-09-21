"""Create document_processing_jobs and processing_artifacts tables.

Revision ID: 0005_processing_pipeline
Revises: 0004_documents_and_storage
Create Date: 2026-09-18 02:56:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_processing_pipeline"
down_revision: Union[str, None] = "0004_documents_and_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_processing_jobs and processing_artifacts tables."""
    # 1. document_processing_jobs
    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processor_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_processing_jobs_created_at"), "document_processing_jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_document_processing_jobs_document_id"), "document_processing_jobs", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_processing_jobs_status"), "document_processing_jobs", ["status"], unique=False)

    # 2. processing_artifacts
    op.create_table(
        "processing_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), server_default="NORMALIZED_CONTENT", nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), server_default="application/json", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_processing_artifacts_artifact_type"), "processing_artifacts", ["artifact_type"], unique=False)
    op.create_index(op.f("ix_processing_artifacts_created_at"), "processing_artifacts", ["created_at"], unique=False)
    op.create_index(op.f("ix_processing_artifacts_document_id"), "processing_artifacts", ["document_id"], unique=False)


def downgrade() -> None:
    """Drop document_processing_jobs and processing_artifacts tables."""
    op.drop_index(op.f("ix_processing_artifacts_document_id"), table_name="processing_artifacts")
    op.drop_index(op.f("ix_processing_artifacts_created_at"), table_name="processing_artifacts")
    op.drop_index(op.f("ix_processing_artifacts_artifact_type"), table_name="processing_artifacts")
    op.drop_table("processing_artifacts")

    op.drop_index(op.f("ix_document_processing_jobs_status"), table_name="document_processing_jobs")
    op.drop_index(op.f("ix_document_processing_jobs_document_id"), table_name="document_processing_jobs")
    op.drop_index(op.f("ix_document_processing_jobs_created_at"), table_name="document_processing_jobs")
    op.drop_table("document_processing_jobs")
