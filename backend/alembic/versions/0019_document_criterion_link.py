"""Add criterion_id column to documents table for bidder document requirement linkage.

Revision ID: 0019_document_criterion_link
Revises: 0018_submission_lifecycle_and_deadline
Create Date: 2026-09-22 01:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019_document_criterion_link"
down_revision: Union[str, None] = "0018_submission_lifecycle_and_deadline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add criterion_id foreign key column to documents table."""
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("criterion_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_documents_criterion_id",
            "tender_criteria",
            ["criterion_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_documents_criterion_id"),
            ["criterion_id"],
            unique=False,
        )


def downgrade() -> None:
    """Revert criterion_id from documents table."""
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_criterion_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_documents_criterion_id"))
        batch_op.drop_column("criterion_id")
