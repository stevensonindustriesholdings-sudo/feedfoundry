"""Rename joboutputtype enum label to match existing UPPER_SNAKE convention.

Revision ID: 005_media_inspection_upper
Revises: 004_media_inspection_enum
Create Date: 2026-05-13

004 added lowercase ``media_inspection``; SQLModel persists Python Enum *names*
(``MEDIA_INSPECTION``) which match labels like ``RAW_TRANSCRIPT``. Rename so inserts succeed.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

revision: str = "005_media_inspection_upper"
down_revision: Union[str, None] = "004_media_inspection_enum"
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
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t ON e.enumtypid = t.oid
    WHERE t.typname = 'joboutputtype'
      AND e.enumlabel = 'media_inspection'
  ) THEN
    ALTER TYPE joboutputtype RENAME VALUE 'media_inspection' TO 'MEDIA_INSPECTION';
  END IF;
END
$outer$;
"""
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        text(
            """
DO $outer$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_enum e
    JOIN pg_type t ON e.enumtypid = t.oid
    WHERE t.typname = 'joboutputtype'
      AND e.enumlabel = 'MEDIA_INSPECTION'
  ) THEN
    ALTER TYPE joboutputtype RENAME VALUE 'MEDIA_INSPECTION' TO 'media_inspection';
  END IF;
END
$outer$;
"""
        )
    )
