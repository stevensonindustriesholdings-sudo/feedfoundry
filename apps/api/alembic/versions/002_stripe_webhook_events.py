"""Add stripe_webhook_events for Stripe idempotency."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "002_stripe_webhook_events"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "stripe_webhook_events" in insp.get_table_names():
        return
    op.create_table(
        "stripe_webhook_events",
        sa.Column("stripe_event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False, server_default="processed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
