"""Add worker_heartbeats table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "003_worker_heartbeats"
down_revision: Union[str, None] = "002_stripe_webhook_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "worker_heartbeats" in insp.get_table_names():
        return
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=256), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hostname", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("app_env", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("git_commit", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("build_timestamp", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("api_version", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats")
