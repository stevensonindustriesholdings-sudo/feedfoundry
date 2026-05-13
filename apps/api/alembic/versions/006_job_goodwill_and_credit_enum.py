"""Add jobs.goodwill_minutes_granted; add GOODWILL_GRANT / GOODWILL_REVOKE to credit transaction enum (PG).

Revision ID: 006_goodwill
Revises: 005_media_inspection_upper
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "006_goodwill"
down_revision: Union[str, None] = "005_media_inspection_upper"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "jobs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("jobs")}
        if "goodwill_minutes_granted" not in cols:
            op.add_column(
                "jobs",
                sa.Column("goodwill_minutes_granted", sa.Integer(), nullable=True),
            )

    if bind.dialect.name != "postgresql":
        return
    if "credit_transactions" not in insp.get_table_names():
        return
    op.execute(
        text(
            """
DO $outer$
DECLARE
  typ text;
BEGIN
  SELECT t.typname INTO typ
  FROM pg_type t
  JOIN pg_attribute a ON a.atttypid = t.oid
  JOIN pg_class c ON a.attrelid = c.oid
  WHERE c.relname = 'credit_transactions'
    AND a.attname = 'type'
  LIMIT 1;

  IF typ IS NULL THEN
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t2 ON e.enumtypid = t2.oid
    WHERE t2.typname = typ
      AND e.enumlabel = 'GOODWILL_GRANT'
  ) THEN
    EXECUTE format('ALTER TYPE %I ADD VALUE %L', typ, 'GOODWILL_GRANT');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t2 ON e.enumtypid = t2.oid
    WHERE t2.typname = typ
      AND e.enumlabel = 'GOODWILL_REVOKE'
  ) THEN
    EXECUTE format('ALTER TYPE %I ADD VALUE %L', typ, 'GOODWILL_REVOKE');
  END IF;
END
$outer$;
"""
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "jobs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("jobs")}
        if "goodwill_minutes_granted" in cols:
            op.drop_column("jobs", "goodwill_minutes_granted")
