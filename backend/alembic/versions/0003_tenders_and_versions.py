"""Create tenders and tender_versions tables.

Revision ID: 0003_tenders_and_versions
Revises: 0002_auth_and_rbac
Create Date: 2026-09-18 02:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_tenders_and_versions"
down_revision: Union[str, None] = "0002_auth_and_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tenders and tender_versions tables."""
    # 1. Create tenders table
    op.create_table(
        "tenders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_number", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("issuing_authority", sa.String(length=255), server_default="Central Reserve Police Force", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="DRAFT", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenders_created_by"), "tenders", ["created_by"], unique=False)
    op.create_index(op.f("ix_tenders_status"), "tenders", ["status"], unique=False)
    op.create_index(op.f("ix_tenders_tender_number"), "tenders", ["tender_number"], unique=True)
    op.create_index(op.f("ix_tenders_title"), "tenders", ["title"], unique=False)

    # 2. Create tender_versions table
    op.create_table(
        "tender_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(length=100), server_default="Initial Release", nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "version_number", name="uq_tender_version_number"),
    )
    op.create_index(op.f("ix_tender_versions_effective_at"), "tender_versions", ["effective_at"], unique=False)
    op.create_index(op.f("ix_tender_versions_is_active"), "tender_versions", ["is_active"], unique=False)
    op.create_index(op.f("ix_tender_versions_tender_id"), "tender_versions", ["tender_id"], unique=False)
    op.create_index(op.f("ix_tender_versions_version_number"), "tender_versions", ["version_number"], unique=False)


def downgrade() -> None:
    """Drop tenders and tender_versions tables."""
    op.drop_index(op.f("ix_tender_versions_version_number"), table_name="tender_versions")
    op.drop_index(op.f("ix_tender_versions_tender_id"), table_name="tender_versions")
    op.drop_index(op.f("ix_tender_versions_is_active"), table_name="tender_versions")
    op.drop_index(op.f("ix_tender_versions_effective_at"), table_name="tender_versions")
    op.drop_table("tender_versions")
    op.drop_index(op.f("ix_tenders_title"), table_name="tenders")
    op.drop_index(op.f("ix_tenders_tender_number"), table_name="tenders")
    op.drop_index(op.f("ix_tenders_status"), table_name="tenders")
    op.drop_index(op.f("ix_tenders_created_by"), table_name="tenders")
    op.drop_table("tenders")
