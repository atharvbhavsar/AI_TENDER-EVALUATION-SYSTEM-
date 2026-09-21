"""Add bidder, bid_submission, evidence_extraction_runs, bidder_evidence tables, and document submission link.

Revision ID: 0008_bidder_evidence_extraction
Revises: 0007_officer_approval_and_history
Create Date: 2026-09-18 03:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_bidder_evidence_extraction"
down_revision: Union[str, None] = "0007_officer_approval_and_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 9 tables and foreign keys."""
    # 1. Create bidders table
    op.create_table(
        "bidders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_code", sa.String(length=50), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "bidder_code", name="uq_tender_bidder_code"),
    )
    op.create_index(op.f("ix_bidders_tender_id"), "bidders", ["tender_id"], unique=False)
    op.create_index(op.f("ix_bidders_bidder_code"), "bidders", ["bidder_code"], unique=False)
    op.create_index(op.f("ix_bidders_legal_name"), "bidders", ["legal_name"], unique=False)

    # 2. Create bid_submissions table
    op.create_table(
        "bid_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("submission_reference", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="RECEIVED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_version_id", "bidder_id", "submission_reference", name="uq_submission_version_bidder_ref"),
    )
    op.create_index(op.f("ix_bid_submissions_tender_version_id"), "bid_submissions", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_bid_submissions_bidder_id"), "bid_submissions", ["bidder_id"], unique=False)
    op.create_index(op.f("ix_bid_submissions_submission_reference"), "bid_submissions", ["submission_reference"], unique=False)
    op.create_index(op.f("ix_bid_submissions_status"), "bid_submissions", ["status"], unique=False)

    # 3. Add bid_submission_id column to documents table
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("bid_submission_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_documents_bid_submission_id", "bid_submissions", ["bid_submission_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_index(batch_op.f("ix_documents_bid_submission_id"), ["bid_submission_id"], unique=False)

    # 4. Create evidence_extraction_runs table
    op.create_table(
        "evidence_extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("extractor_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_extraction_runs_bid_submission_id"), "evidence_extraction_runs", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_evidence_extraction_runs_criterion_id"), "evidence_extraction_runs", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_evidence_extraction_runs_status"), "evidence_extraction_runs", ["status"], unique=False)
    op.create_index(op.f("ix_evidence_extraction_runs_created_at"), "evidence_extraction_runs", ["created_at"], unique=False)

    # 5. Create bidder_evidence table
    op.create_table(
        "bidder_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=50), server_default="DOCUMENT", nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_value", sa.Float(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("period", sa.String(length=50), nullable=True),
        sa.Column("date_value", sa.String(length=50), nullable=True),
        sa.Column("certificate_data", sa.JSON(), nullable=True),
        sa.Column("experience_data", sa.JSON(), nullable=True),
        sa.Column("extracted_bidder_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="FOUND", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_block_id", sa.String(length=100), nullable=True),
        sa.Column("source_table_reference", sa.String(length=100), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("raw_extracted_data", sa.JSON(), nullable=True),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column("extractor_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["evidence_extraction_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bidder_evidence_criterion_id"), "bidder_evidence", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_bidder_evidence_bid_submission_id"), "bidder_evidence", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_bidder_evidence_document_id"), "bidder_evidence", ["document_id"], unique=False)
    op.create_index(op.f("ix_bidder_evidence_extraction_run_id"), "bidder_evidence", ["extraction_run_id"], unique=False)
    op.create_index(op.f("ix_bidder_evidence_status"), "bidder_evidence", ["status"], unique=False)
    op.create_index(op.f("ix_bidder_evidence_created_at"), "bidder_evidence", ["created_at"], unique=False)


def downgrade() -> None:
    """Revert Phase 9 changes."""
    op.drop_table("bidder_evidence")
    op.drop_table("evidence_extraction_runs")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_bid_submission_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_documents_bid_submission_id"))
        batch_op.drop_column("bid_submission_id")
    op.drop_table("bid_submissions")
    op.drop_table("bidders")
