"""Add review_cases, review_items, officer_decisions, review_notes, review_audit_logs for Phase 13.

Revision ID: 0012_human_review_and_decisions
Revises: 0011_bidder_overall_evaluations
Create Date: 2026-09-18 17:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_human_review_and_decisions"
down_revision: Union[str, None] = "0011_bidder_overall_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 13 human review and decision tables."""
    # 1. review_cases
    op.create_table(
        "review_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("overall_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("priority", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column("issue_type", sa.String(length=50), server_default="MANUAL_REVIEW_REQUIRED", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criterion_evaluation_id"], ["criterion_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["overall_evaluation_id"], ["bidder_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_cases_tender_id"), "review_cases", ["tender_id"], unique=False)
    op.create_index(op.f("ix_review_cases_tender_version_id"), "review_cases", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_review_cases_bidder_id"), "review_cases", ["bidder_id"], unique=False)
    op.create_index(op.f("ix_review_cases_bid_submission_id"), "review_cases", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_review_cases_criterion_id"), "review_cases", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_review_cases_status"), "review_cases", ["status"], unique=False)
    op.create_index(op.f("ix_review_cases_priority"), "review_cases", ["priority"], unique=False)
    op.create_index(op.f("ix_review_cases_assigned_to"), "review_cases", ["assigned_to"], unique=False)
    op.create_index("ix_review_cases_scope", "review_cases", ["tender_version_id", "bidder_id", "bid_submission_id"], unique=False)
    op.create_index("ix_review_cases_status_priority", "review_cases", ["status", "priority"], unique=False)

    # 2. review_items
    op.create_table(
        "review_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_case_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("issue_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criterion_evaluation_id"], ["criterion_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_id"], ["bidder_evidence.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_items_review_case_id"), "review_items", ["review_case_id"], unique=False)

    # 3. officer_decisions
    op.create_table(
        "officer_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_case_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("system_result", sa.String(length=50), nullable=False),
        sa.Column("final_verdict", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("officer_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["criterion_evaluation_id"], ["criterion_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["officer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_officer_decisions_review_case_id"), "officer_decisions", ["review_case_id"], unique=False)
    op.create_index(op.f("ix_officer_decisions_officer_id"), "officer_decisions", ["officer_id"], unique=False)
    op.create_index(op.f("ix_officer_decisions_decision"), "officer_decisions", ["decision"], unique=False)

    # 4. review_notes
    op.create_table(
        "review_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_case_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_notes_review_case_id"), "review_notes", ["review_case_id"], unique=False)

    # 5. review_audit_logs
    op.create_table(
        "review_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_case_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_audit_logs_review_case_id"), "review_audit_logs", ["review_case_id"], unique=False)


def downgrade() -> None:
    """Revert Phase 13 review tables."""
    op.drop_table("review_audit_logs")
    op.drop_table("review_notes")
    op.drop_table("officer_decisions")
    op.drop_table("review_items")
    op.drop_table("review_cases")
