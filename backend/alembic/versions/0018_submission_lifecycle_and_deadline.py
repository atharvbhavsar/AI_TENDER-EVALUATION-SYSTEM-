"""Add submission deadline to tenders and lifecycle fields to bid_submissions.

Revision ID: 0018_submission_lifecycle_and_deadline
Revises: 0017_bidder_portal_and_user_link
Create Date: 2026-09-22 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0018_submission_lifecycle_and_deadline"
down_revision: Union[str, None] = "0017_bidder_portal_and_user_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tender deadline and submission lifecycle fields."""
    op.add_column("tenders", sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_tenders_submission_deadline"), "tenders", ["submission_deadline"], unique=False)

    op.add_column("bid_submissions", sa.Column("bidder_notes", sa.Text(), nullable=True))
    op.add_column("bid_submissions", sa.Column("commercial_quote", sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column("bid_submissions", sa.Column("declaration_signed", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("bid_submissions", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bid_submissions", sa.Column("is_locked", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    """Revert tender deadline and submission lifecycle fields."""
    op.drop_column("bid_submissions", "is_locked")
    op.drop_column("bid_submissions", "submitted_at")
    op.drop_column("bid_submissions", "declaration_signed")
    op.drop_column("bid_submissions", "commercial_quote")
    op.drop_column("bid_submissions", "bidder_notes")
    op.drop_index(op.f("ix_tenders_submission_deadline"), table_name="tenders")
    op.drop_column("tenders", "submission_deadline")
