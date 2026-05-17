"""Repair ``jobstatus`` PG labels to match SQLAlchemy ``Enum(JobStatus)`` member names.

Revision ID: 008_jobstatus_sqlalchemy_labels
Revises: 007_youtube_source_queue
Create Date: 2026-05-14

006 briefly emitted six lowercase PostgreSQL enum labels (``uploaded``, …) matching ``str``
values. SQLAlchemy maps native PG enums to Python members using ``Enum.name`` (``UPLOADED``, …),
so ORM loads failed with ``LookupError``. This revision is idempotent and no-ops once ``UPLOADED``
exists as a label.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "008_jobstatus_sqlalchemy_labels"
down_revision: Union[str, None] = "007_youtube_source_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    has_value_style = bind.execute(
        text(
            """
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'jobstatus' AND e.enumlabel = 'uploaded'
            LIMIT 1
            """
        )
    ).fetchone()
    if has_value_style is None:
        return

    op.execute(
        text(
            "ALTER TABLE jobs ALTER COLUMN status TYPE VARCHAR(64) USING (status::text)"
        )
    )
    op.execute(text("DROP TYPE jobstatus"))
    op.execute(
        text(
            "CREATE TYPE jobstatus AS ENUM ("
            "'UPLOADED', 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED')"
        )
    )
    op.execute(
        text(
            """
            UPDATE jobs SET status = CASE status
              WHEN 'uploaded' THEN 'UPLOADED'
              WHEN 'queued' THEN 'QUEUED'
              WHEN 'processing' THEN 'PROCESSING'
              WHEN 'completed' THEN 'COMPLETED'
              WHEN 'failed' THEN 'FAILED'
              WHEN 'cancelled' THEN 'CANCELLED'
              ELSE 'PROCESSING'
            END
            WHERE status IN (
              'uploaded','queued','processing','completed','failed','cancelled'
            )
            """
        )
    )
    op.execute(
        text(
            "ALTER TABLE jobs ALTER COLUMN status TYPE jobstatus USING (status::jobstatus)"
        )
    )


def downgrade() -> None:
    pass
