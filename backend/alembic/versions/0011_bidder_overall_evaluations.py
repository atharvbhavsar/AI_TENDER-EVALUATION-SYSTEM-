"""Add bidder_evaluations table for Phase 12 overall eligibility aggregation.

Revision ID: 0011_bidder_overall_evaluations
Revises: 0010_deterministic_rules_and_evaluations
Create Date: 2026-09-18 17:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_bidder_overall_evaluations"
down_revision: Union[str, None] = "0010_deterministic_rules_and_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 12 bidder_evaluations table and associated indexes."""
    op.create_table(
        "bidder_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("aggregation_policy_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("criterion_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("not_eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("manual_review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mandatory_criterion_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mandatory_eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mandatory_not_eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mandatory_manual_review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("optional_criterion_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("optional_eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("optional_not_eligible_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("optional_manual_review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rule_version_snapshot", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("evaluated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bidder_evaluations_tender_id"), "bidder_evaluations", ["tender_id"], unique=False)
    op.create_index(op.f("ix_bidder_evaluations_tender_version_id"), "bidder_evaluations", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_bidder_evaluations_bidder_id"), "bidder_evaluations", ["bidder_id"], unique=False)
    op.create_index(op.f("ix_bidder_evaluations_bid_submission_id"), "bidder_evaluations", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_bidder_evaluations_evaluation_run_id"), "bidder_evaluations", ["evaluation_run_id"], unique=False)
    op.create_index(op.f("ix_bidder_evaluations_result"), "bidder_evaluations", ["result"], unique=False)
    op.create_index("ix_bidder_eval_scope", "bidder_evaluations", ["tender_version_id", "bidder_id", "bid_submission_id"], unique=False)


def downgrade() -> None:
    """Revert Phase 12 bidder_evaluations table."""
    op.drop_index("ix_bidder_eval_scope", table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_result"), table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_evaluation_run_id"), table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_bid_submission_id"), table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_bidder_id"), table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_tender_version_id"), table_name="bidder_evaluations")
    op.drop_index(op.f("ix_bidder_evaluations_tender_id"), table_name="bidder_evaluations")
    op.drop_table("bidder_evaluations")
