"""Add bidder portal user links and profile fields.

Revision ID: 0017_bidder_portal_and_user_link
Revises: 0016_multi_bidder_ranking
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017_bidder_portal_and_user_link"
down_revision: Union[str, None] = "0016_multi_bidder_ranking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile fields to users and user_id link to bidders."""
    op.add_column("users", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))

    op.add_column("bidders", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_bidders_user_id"), "bidders", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_bidders_user_id_users",
        "bidders",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Revert user profile fields and bidder user_id link."""
    op.drop_constraint("fk_bidders_user_id_users", "bidders", type_="foreignkey")
    op.drop_index(op.f("ix_bidders_user_id"), table_name="bidders")
    op.drop_column("bidders", "user_id")
    op.drop_column("users", "phone")
    op.drop_column("users", "company_name")
