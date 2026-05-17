"""Idempotent: add legacy ``created`` label to ``jobstatus`` enum (optional tooling parity).

Revision ID: 009_jobstatus_created_enum_label
Revises: 008_jobstatus_sqlalchemy_labels
Create Date: 2026-05-17

006 normalizes legacy rows via ``status::text`` so ``IN (...)`` does not coerce unknown
labels through the enum parser. This revision remains useful for databases that predate
that fix or for ad-hoc SQL comparing to the literal label.

PostgreSQL before 15 has no ``ADD VALUE IF NOT EXISTS``; use ``pg_enum`` guard + DO block.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "009_jobstatus_created_enum_label"
down_revision: Union[str, None] = "008_jobstatus_sqlalchemy_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        text(
            """
            DO $jobstatus_add_created$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_enum e
                JOIN pg_catalog.pg_type t ON t.oid = e.enumtypid
                JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = pg_catalog.current_schema()
                  AND t.typname = 'jobstatus'
                  AND e.enumlabel = 'created'
              ) THEN
                ALTER TYPE jobstatus ADD VALUE 'created';
              END IF;
            END
            $jobstatus_add_created$;
            """
        )
    )


def downgrade() -> None:
    # Enum labels cannot be dropped safely in-place; leave type unchanged.
    pass
