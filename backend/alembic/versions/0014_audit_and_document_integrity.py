"""Add evidence_id, evaluation_id, and review_id columns and indices to audit_logs for Phase 16.

Revision ID: 0014_audit_and_document_integrity
Revises: 0013_audit_and_evaluation_reports
Create Date: 2026-09-18 19:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014_audit_and_document_integrity"
down_revision: Union[str, None] = "0013_audit_and_evaluation_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 16 scoping columns and indexes to audit_logs table."""
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("evidence_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("evaluation_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("review_id", sa.Uuid(), nullable=True))

        batch_op.create_foreign_key(
            "fk_audit_logs_evidence_id",
            "bidder_evidence",
            ["evidence_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_audit_logs_evaluation_id",
            "criterion_evaluations",
            ["evaluation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_audit_logs_review_id",
            "review_cases",
            ["review_id"],
            ["id"],
            ondelete="SET NULL",
        )

        batch_op.create_index("ix_audit_logs_evidence_id", ["evidence_id"], unique=False)
        batch_op.create_index("ix_audit_logs_evaluation_id", ["evaluation_id"], unique=False)
        batch_op.create_index("ix_audit_logs_review_id", ["review_id"], unique=False)


def downgrade() -> None:
    """Remove Phase 16 columns and indices from audit_logs."""
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_review_id")
        batch_op.drop_index("ix_audit_logs_evaluation_id")
        batch_op.drop_index("ix_audit_logs_evidence_id")

        batch_op.drop_constraint("fk_audit_logs_review_id", type_="foreignkey")
        batch_op.drop_constraint("fk_audit_logs_evaluation_id", type_="foreignkey")
        batch_op.drop_constraint("fk_audit_logs_evidence_id", type_="foreignkey")

        batch_op.drop_column("review_id")
        batch_op.drop_column("evaluation_id")
        batch_op.drop_column("evidence_id")
