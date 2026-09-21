"""Add approval lifecycle, original extraction snapshots, and criterion_approval_history table.

Revision ID: 0007_officer_approval_and_history
Revises: 0006_criterion_extraction
Create Date: 2026-09-18 03:13:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_officer_approval_and_history"
down_revision: Union[str, None] = "0006_criterion_extraction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add approval fields and create criterion_approval_history table."""
    # 1. Add approval and original extraction snapshot columns to tender_criteria
    with op.batch_alter_table("tender_criteria") as batch_op:
        batch_op.add_column(sa.Column("approval_status", sa.String(length=50), server_default="PENDING_REVIEW", nullable=False))
        batch_op.add_column(sa.Column("approved_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("is_corrected", sa.Boolean(), server_default=sa.text("false"), nullable=False))

        # Original AI Extraction Snapshot columns
        batch_op.add_column(sa.Column("original_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("original_description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("original_category", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("original_requirement_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("original_operator", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("original_threshold_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("original_threshold_text", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("original_unit", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("original_currency", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("original_period", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("original_mandatory", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("original_required_evidence", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("original_source_clause", sa.Text(), nullable=True))

        batch_op.create_foreign_key("fk_tender_criteria_approved_by", "users", ["approved_by"], ["id"], ondelete="SET NULL")
        batch_op.create_index(op.f("ix_tender_criteria_approval_status"), ["approval_status"], unique=False)
        batch_op.create_index("ix_tender_criteria_version_approval", ["tender_version_id", "approval_status"], unique=False)

    # 2. Create criterion_approval_history table
    op.create_table(
        "criterion_approval_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=50), nullable=False),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("officer_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["criterion_id"], ["tender_criteria.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["officer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_criterion_approval_history_action"), "criterion_approval_history", ["action"], unique=False)
    op.create_index(op.f("ix_criterion_approval_history_created_at"), "criterion_approval_history", ["created_at"], unique=False)
    op.create_index(op.f("ix_criterion_approval_history_criterion_id"), "criterion_approval_history", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_criterion_approval_history_officer_id"), "criterion_approval_history", ["officer_id"], unique=False)


def downgrade() -> None:
    """Drop criterion_approval_history table and approval columns from tender_criteria."""
    op.drop_index(op.f("ix_criterion_approval_history_officer_id"), table_name="criterion_approval_history")
    op.drop_index(op.f("ix_criterion_approval_history_criterion_id"), table_name="criterion_approval_history")
    op.drop_index(op.f("ix_criterion_approval_history_created_at"), table_name="criterion_approval_history")
    op.drop_index(op.f("ix_criterion_approval_history_action"), table_name="criterion_approval_history")
    op.drop_table("criterion_approval_history")

    with op.batch_alter_table("tender_criteria") as batch_op:
        batch_op.drop_index("ix_tender_criteria_version_approval")
        batch_op.drop_index(op.f("ix_tender_criteria_approval_status"))
        batch_op.drop_constraint("fk_tender_criteria_approved_by", type_="foreignkey")
        batch_op.drop_column("original_source_clause")
        batch_op.drop_column("original_required_evidence")
        batch_op.drop_column("original_mandatory")
        batch_op.drop_column("original_period")
        batch_op.drop_column("original_currency")
        batch_op.drop_column("original_unit")
        batch_op.drop_column("original_threshold_text")
        batch_op.drop_column("original_threshold_value")
        batch_op.drop_column("original_operator")
        batch_op.drop_column("original_requirement_type")
        batch_op.drop_column("original_category")
        batch_op.drop_column("original_description")
        batch_op.drop_column("original_name")
        batch_op.drop_column("is_corrected")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by")
        batch_op.drop_column("approval_status")
