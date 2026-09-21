"""Initial database baseline migration.

Revision ID: 0001_initial_baseline
Revises: 
Create Date: 2026-09-18 02:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline upgrade - expand alembic_version version_num column length if on supporting dialect."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            type_=sa.String(128),
            existing_type=sa.String(32),
        )


def downgrade() -> None:
    """Baseline downgrade."""
    pass

