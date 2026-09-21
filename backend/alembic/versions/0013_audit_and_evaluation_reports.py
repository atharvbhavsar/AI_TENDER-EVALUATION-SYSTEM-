"""Add audit_logs and evaluation_reports tables for Phase 14.

Revision ID: 0013_audit_and_evaluation_reports
Revises: 0012_human_review_and_decisions
Create Date: 2026-09-18 18:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013_audit_and_evaluation_reports"
down_revision: Union[str, None] = "0012_human_review_and_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 14 system audit logs and evaluation reports tables."""
    # 1. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("tender_id", sa.Uuid(), nullable=True),
        sa.Column("tender_version_id", sa.Uuid(), nullable=True),
        sa.Column("bidder_id", sa.Uuid(), nullable=True),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("document_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("source_service", sa.String(length=50), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_bid_submission_id", "audit_logs", ["bid_submission_id"])
    op.create_index("ix_audit_logs_bidder_id", "audit_logs", ["bidder_id"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
    op.create_index("ix_audit_logs_criterion_id", "audit_logs", ["criterion_id"])
    op.create_index("ix_audit_logs_document_id", "audit_logs", ["document_id"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_tender_id", "audit_logs", ["tender_id"])
    op.create_index("ix_audit_logs_tender_version_id", "audit_logs", ["tender_version_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_scope", "audit_logs", ["tender_id", "tender_version_id", "bidder_id", "bid_submission_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_action_ts", "audit_logs", ["action", "timestamp"])

    # 2. evaluation_reports
    op.create_table(
        "evaluation_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=True),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=True),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=True),
        sa.Column("overall_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("generated_by", sa.Uuid(), nullable=True),
        sa.Column("generation_metadata", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["overall_evaluation_id"], ["bidder_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_reports_scope", "evaluation_reports", ["tender_version_id", "bidder_id", "bid_submission_id"])
    op.create_index("ix_eval_reports_type_status", "evaluation_reports", ["report_type", "status"])
    op.create_index("ix_evaluation_reports_bid_submission_id", "evaluation_reports", ["bid_submission_id"])
    op.create_index("ix_evaluation_reports_bidder_id", "evaluation_reports", ["bidder_id"])
    op.create_index("ix_evaluation_reports_created_at", "evaluation_reports", ["created_at"])
    op.create_index("ix_evaluation_reports_evaluation_run_id", "evaluation_reports", ["evaluation_run_id"])
    op.create_index("ix_evaluation_reports_overall_evaluation_id", "evaluation_reports", ["overall_evaluation_id"])
    op.create_index("ix_evaluation_reports_report_type", "evaluation_reports", ["report_type"])
    op.create_index("ix_evaluation_reports_status", "evaluation_reports", ["status"])
    op.create_index("ix_evaluation_reports_tender_id", "evaluation_reports", ["tender_id"])
    op.create_index("ix_evaluation_reports_tender_version_id", "evaluation_reports", ["tender_version_id"])


def downgrade() -> None:
    """Downgrade Phase 14 tables."""
    op.drop_table("evaluation_reports")
    op.drop_table("audit_logs")
