"""Add tender_evaluation_methods and bidder_rankings tables for multi-bidder ranking.

Revision ID: 0016_multi_bidder_ranking
Revises: 0015_redis_job_enhancement
Create Date: 2026-09-21 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_multi_bidder_ranking"
down_revision: Union[str, None] = "0015_redis_job_enhancement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tender_evaluation_methods and bidder_rankings tables."""
    op.create_table(
        "tender_evaluation_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("method_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("financial_weight", sa.Float(), nullable=True),
        sa.Column("technical_weight", sa.Float(), nullable=True),
        sa.Column("minimum_technical_score", sa.Float(), nullable=True),
        sa.Column("ranking_direction", sa.String(length=20), nullable=False, server_default="ASCENDING"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
        sa.Column("tie_breaker_rule", sa.String(length=100), nullable=True, server_default="HUMAN_REVIEW"),
        sa.Column("version", sa.String(length=50), nullable=False, server_default="v1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_version_id", "version", name="uq_tender_version_eval_method"),
    )
    op.create_index(
        "ix_eval_method_tender_version",
        "tender_evaluation_methods",
        ["tender_version_id"],
        unique=False,
    )

    op.create_table(
        "bidder_rankings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("tender_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("bidder_id", sa.Uuid(), nullable=False),
        sa.Column("bid_submission_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_method", sa.String(length=50), nullable=False, server_default="L1"),
        sa.Column("eligibility_status", sa.String(length=50), nullable=False),
        sa.Column("quoted_price", sa.Float(), nullable=True),
        sa.Column("evaluated_price", sa.Float(), nullable=True),
        sa.Column("technical_score", sa.Float(), nullable=True),
        sa.Column("financial_score", sa.Float(), nullable=True),
        sa.Column("combined_score", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rank_label", sa.String(length=20), nullable=True),
        sa.Column("ranking_status", sa.String(length=50), nullable=False, server_default="QUALIFIED_RANKED"),
        sa.Column("calculation_details", sa.JSON(), nullable=False),
        sa.Column("provenance_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_version_id"], ["tender_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bidder_id"], ["bidders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bid_submission_id"], ["bid_submissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bidder_rankings_scope",
        "bidder_rankings",
        ["tender_version_id", "evaluation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_bidder_rankings_bidder",
        "bidder_rankings",
        ["bidder_id"],
        unique=False,
    )
    op.create_index(
        "ix_bidder_rankings_rank",
        "bidder_rankings",
        ["tender_version_id", "rank"],
        unique=False,
    )


def downgrade() -> None:
    """Drop bidder_rankings and tender_evaluation_methods tables."""
    op.drop_index("ix_bidder_rankings_rank", table_name="bidder_rankings")
    op.drop_index("ix_bidder_rankings_bidder", table_name="bidder_rankings")
    op.drop_index("ix_bidder_rankings_scope", table_name="bidder_rankings")
    op.drop_table("bidder_rankings")
    op.drop_index("ix_eval_method_tender_version", table_name="tender_evaluation_methods")
    op.drop_table("tender_evaluation_methods")
