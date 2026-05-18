"""Add joboutputtype enum value AGENT_BUNDLE.

Revision ID: 013_agent_bundle_enum
Revises: 012_seed_smoke_org
Create Date: 2026-05-18

PostgreSQL enum labels must match SQLAlchemy/SQLModel Enum member names.
``JobOutputType.AGENT_BUNDLE`` is stored as ``AGENT_BUNDLE`` in production.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

revision: str = "013_agent_bundle_enum"
down_revision: Union[str, None] = "012_seed_smoke_org"
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
      AND e.enumlabel = 'AGENT_BUNDLE'
  ) THEN
    EXECUTE format('ALTER TYPE %I ADD VALUE %L', typ, 'AGENT_BUNDLE');
  END IF;
END
$outer$;
"""
        )
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping individual enum values safely.
    pass
