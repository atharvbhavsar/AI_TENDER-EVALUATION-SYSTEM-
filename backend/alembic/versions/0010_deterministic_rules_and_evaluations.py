"""Add criterion_rules and criterion_evaluations tables for Phase 11.

Revision ID: 0010_deterministic_rules_and_evaluations
Revises: 0009_hybrid_retrieval_and_chunks
Create Date: 2026-09-18 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_deterministic_rules_and_evaluations"
down_revision: Union[str, None] = "0009_hybrid_retrieval_and_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Phase 11 criterion_rules and criterion_evaluations tables."""
    # 1. Create criterion_rules table
    op.create_table(
        "criterion_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("rule_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("template_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("rego_policy_reference", sa.String(length=100), server_default="crpf.evaluation.main", nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_criterion_rules_criterion_id"), "criterion_rules", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_criterion_rules_tender_version_id"), "criterion_rules", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_criterion_rules_rule_type"), "criterion_rules", ["rule_type"], unique=False)
    op.create_index(op.f("ix_criterion_rules_status"), "criterion_rules", ["status"], unique=False)
    op.create_index("ix_criterion_rules_version_type", "criterion_rules", ["tender_version_id", "rule_type"], unique=False)

    # 2. Create criterion_evaluations table
    op.create_table(
        "criterion_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("rule_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=True),
        sa.Column("evaluated_by", sa.Uuid(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rule_id"], ["criterion_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_criterion_evaluations_criterion_id"), "criterion_evaluations", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_bidder_id"), "criterion_evaluations", ["bidder_id"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_bid_submission_id"), "criterion_evaluations", ["bid_submission_id"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_tender_version_id"), "criterion_evaluations", ["tender_version_id"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_rule_id"), "criterion_evaluations", ["rule_id"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_result"), "criterion_evaluations", ["result"], unique=False)
    op.create_index(op.f("ix_criterion_evaluations_evaluation_run_id"), "criterion_evaluations", ["evaluation_run_id"], unique=False)
    op.create_index("ix_eval_submission_criterion", "criterion_evaluations", ["bid_submission_id", "criterion_id"], unique=False)
    op.create_index("ix_eval_scope", "criterion_evaluations", ["tender_version_id", "bidder_id", "bid_submission_id"], unique=False)


def downgrade() -> None:
    """Revert Phase 11 changes."""
    op.drop_index("ix_eval_scope", table_name="criterion_evaluations")
    op.drop_index("ix_eval_submission_criterion", table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_evaluation_run_id"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_result"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_rule_id"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_tender_version_id"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_bid_submission_id"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_bidder_id"), table_name="criterion_evaluations")
    op.drop_index(op.f("ix_criterion_evaluations_criterion_id"), table_name="criterion_evaluations")
    op.drop_table("criterion_evaluations")

    op.drop_index("ix_criterion_rules_version_type", table_name="criterion_rules")
    op.drop_index(op.f("ix_criterion_rules_status"), table_name="criterion_rules")
    op.drop_index(op.f("ix_criterion_rules_rule_type"), table_name="criterion_rules")
    op.drop_index(op.f("ix_criterion_rules_tender_version_id"), table_name="criterion_rules")
    op.drop_index(op.f("ix_criterion_rules_criterion_id"), table_name="criterion_rules")
    op.drop_table("criterion_rules")
