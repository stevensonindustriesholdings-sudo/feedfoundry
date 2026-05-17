"""Add youtube_source_queue for URL enqueue scaffold (no ingestion).

Revision ID: 007_youtube_source_queue
Revises: 006_processing_minutes
Create Date: 2026-05-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "007_youtube_source_queue"
down_revision: Union[str, None] = "006_processing_minutes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "youtube_source_queue" in insp.get_table_names():
        return
    op.create_table(
        "youtube_source_queue",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.String(), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("youtube_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_youtube_queue_org_status", "youtube_source_queue", ["organisation_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "youtube_source_queue" not in insp.get_table_names():
        return
    op.drop_index("ix_youtube_queue_org_status", table_name="youtube_source_queue")
    op.drop_table("youtube_source_queue")
