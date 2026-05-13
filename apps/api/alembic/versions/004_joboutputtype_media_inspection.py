"""Add joboutputtype enum value media_inspection (PostgreSQL only).

Revision ID: 004_media_inspection_enum
Revises: 003_worker_heartbeats
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "004_media_inspection_enum"
down_revision: Union[str, None] = "003_worker_heartbeats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = inspect(bind)
    if "job_outputs" not in insp.get_table_names():
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
  WHERE c.relname = 'job_outputs'
    AND a.attname = 'output_type'
  LIMIT 1;

  IF typ IS NULL THEN
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t2 ON e.enumtypid = t2.oid
    WHERE t2.typname = typ
      AND e.enumlabel = 'media_inspection'
  ) THEN
    EXECUTE format('ALTER TYPE %I ADD VALUE %L', typ, 'media_inspection');
  END IF;
END
$outer$;
"""
        )
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping individual enum values safely.
    pass
