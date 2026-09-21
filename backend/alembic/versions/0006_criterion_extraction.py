"""Create extraction_runs, tender_criteria, and criterion_source_references tables.

Revision ID: 0006_criterion_extraction
Revises: 0005_processing_pipeline
Create Date: 2026-09-18 03:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_criterion_extraction"
down_revision: Union[str, None] = "0005_processing_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create extraction_runs, tender_criteria, and criterion_source_references tables."""
    # 1. extraction_runs
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("extractor_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("criteria_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extraction_runs_created_at"), "extraction_runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_extraction_runs_created_by"), "extraction_runs", ["created_by"], unique=False)
    op.create_index(op.f("ix_extraction_runs_status"), "extraction_runs", ["status"], unique=False)
    op.create_index(op.f("ix_extraction_runs_tender_version_id"), "extraction_runs", ["tender_version_id"], unique=False)

    # 2. tender_criteria
    op.create_table(
        "tender_criteria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("requirement_type", sa.String(length=50), nullable=False),
        sa.Column("condition_text", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(length=20), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("threshold_text", sa.String(length=255), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=20), nullable=True),
        sa.Column("period", sa.String(length=255), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=True),
        sa.Column("required_evidence", sa.JSON(), nullable=True),
        sa.Column("source_clause", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_section", sa.String(length=255), nullable=True),
        sa.Column("source_block_id", sa.String(length=100), nullable=True),
        sa.Column("source_table_reference", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("extraction_status", sa.String(length=50), server_default="EXTRACTED", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_version_id", "criterion_code", name="uq_tender_version_criterion_code"),
    )
    op.create_index(op.f("ix_tender_criteria_category"), "tender_criteria", ["category"], unique=False)
    op.create_index(op.f("ix_tender_criteria_created_at"), "tender_criteria", ["created_at"], unique=False)
    op.create_index(op.f("ix_tender_criteria_criterion_code"), "tender_criteria", ["criterion_code"], unique=False)
    op.create_index(op.f("ix_tender_criteria_extraction_run_id"), "tender_criteria", ["extraction_run_id"], unique=False)
    op.create_index(op.f("ix_tender_criteria_extraction_status"), "tender_criteria", ["extraction_status"], unique=False)
    op.create_index(op.f("ix_tender_criteria_requirement_type"), "tender_criteria", ["requirement_type"], unique=False)
    op.create_index(op.f("ix_tender_criteria_tender_version_id"), "tender_criteria", ["tender_version_id"], unique=False)
    op.create_index("ix_tender_criteria_version_category", "tender_criteria", ["tender_version_id", "category"], unique=False)

    # 3. criterion_source_references
    op.create_table(
        "criterion_source_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("block_id", sa.String(length=100), nullable=True),
        sa.Column("table_reference", sa.String(length=100), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_criterion_source_references_criterion_id"), "criterion_source_references", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_criterion_source_references_document_id"), "criterion_source_references", ["document_id"], unique=False)


def downgrade() -> None:
    """Drop criterion_source_references, tender_criteria, and extraction_runs tables."""
    op.drop_index(op.f("ix_criterion_source_references_document_id"), table_name="criterion_source_references")
    op.drop_index(op.f("ix_criterion_source_references_criterion_id"), table_name="criterion_source_references")
    op.drop_table("criterion_source_references")

    op.drop_index("ix_tender_criteria_version_category", table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_tender_version_id"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_requirement_type"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_extraction_status"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_extraction_run_id"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_criterion_code"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_created_at"), table_name="tender_criteria")
    op.drop_index(op.f("ix_tender_criteria_category"), table_name="tender_criteria")
    op.drop_table("tender_criteria")

    op.drop_index(op.f("ix_extraction_runs_tender_version_id"), table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_status"), table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_created_by"), table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_created_at"), table_name="extraction_runs")
    op.drop_table("extraction_runs")
