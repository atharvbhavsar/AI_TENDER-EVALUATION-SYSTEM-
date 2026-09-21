"""Add job_type, priority, failed_at, and worker_id columns to document_processing_jobs.

Revision ID: 0015_redis_job_enhancement
Revises: 0014_audit_and_document_integrity
Create Date: 2026-09-21 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0015_redis_job_enhancement"
down_revision: Union[str, None] = "0014_audit_and_document_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add job_type, priority, failed_at, and worker_id to document_processing_jobs."""
    with op.batch_alter_table("document_processing_jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "job_type",
                sa.String(length=50),
                server_default="DOCUMENT_PROCESSING",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "failed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "worker_id",
                sa.String(length=100),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_document_processing_jobs_job_type",
            ["job_type"],
            unique=False,
        )


def downgrade() -> None:
    """Drop job_type, priority, failed_at, and worker_id from document_processing_jobs."""
    with op.batch_alter_table("document_processing_jobs") as batch_op:
        batch_op.drop_index("ix_document_processing_jobs_job_type")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("failed_at")
        batch_op.drop_column("priority")
        batch_op.drop_column("job_type")
