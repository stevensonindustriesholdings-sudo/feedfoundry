"""Initial schema from SQLModel metadata (Postgres/SQLite).

Revision ID: 001_initial
Revises:
Create Date: 2026-05-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlmodel import SQLModel

from app.models import (  # noqa: F401
    AIUsageLog,
    AnnualAccess,
    CreditTransaction,
    CreditWallet,
    Job,
    JobOutput,
    MediaAsset,
    Organisation,
    ProviderConfig,
    StripeWebhookEvent,
    User,
    WorkerHeartbeat,
)

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if "organisations" not in tables:
        SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
