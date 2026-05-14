"""Rename wallet/job columns to processing minutes; normalize job statuses; add output/media fields.

Revision ID: 006_processing_minutes
Revises: 005_media_inspection_upper
Create Date: 2026-05-13

PostgreSQL-only data migration (SQLite tests use SQLModel.create_all).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "006_processing_minutes"
down_revision: Union[str, None] = "005_media_inspection_upper"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _pg_jobstatus_enum_label_count(bind) -> int:
    row = bind.execute(
        text(
            """
            SELECT COUNT(*)::int FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'jobstatus'
            """
        )
    ).scalar()
    return int(row or 0)


def _pg_jobstatus_has_created_label(bind) -> bool:
    row = bind.execute(
        text(
            """
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'jobstatus' AND e.enumlabel = 'CREATED'
            LIMIT 1
            """
        )
    ).fetchone()
    return row is not None


def _jobs_status_column_meta(bind):
    return bind.execute(
        text(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'status'
            """
        )
    ).fetchone()


def _migrate_legacy_railway_jobstatus_enum(bind) -> None:
    """v0.1 Railway bridge: older DBs used a native ``jobstatus`` enum with UPPERCASE pipeline labels.

    SQLModel ``JobStatus`` persists lowercase values (``uploaded``, ``completed``, …) that are not
    members of that legacy enum, so ``UPDATE … SET status = 'uploaded'`` fails before this repair.

    Repair: cast through VARCHAR with ``lower(status::text)``, drop the wide enum, recreate a
    6-label enum matching ``app.models.JobStatus``, map legacy literals (including ``complete`` /
    ``COMPLETE``), then cast the column back to ``jobstatus``. Idempotent for re-runs and partial
    failures (orphaned ``jobstatus`` type, VARCHAR column left unattached, etc.).
    """
    insp = inspect(bind)
    if "jobs" not in insp.get_table_names():
        return

    meta = _jobs_status_column_meta(bind)
    if not meta:
        return
    data_type, udt_name = meta[0], meta[1]
    enum_n = _pg_jobstatus_enum_label_count(bind)

    # Already on the slim enum used by current models.
    if data_type == "USER-DEFINED" and udt_name == "jobstatus":
        if enum_n == 6 and not _pg_jobstatus_has_created_label(bind):
            return

    wide_or_legacy = enum_n > 6 or _pg_jobstatus_has_created_label(bind)

    if wide_or_legacy:
        if data_type == "USER-DEFINED" and udt_name == "jobstatus":
            op.execute(
                text(
                    "ALTER TABLE jobs ALTER COLUMN status TYPE VARCHAR(64) "
                    "USING (lower(status::text))"
                )
            )
        if _pg_jobstatus_enum_label_count(bind) > 0:
            op.execute(text("DROP TYPE jobstatus"))
        op.execute(
            text(
                "CREATE TYPE jobstatus AS ENUM ("
                "'uploaded', 'queued', 'processing', 'completed', 'failed', 'cancelled')"
            )
        )
        op.execute(
            text(
                """
                UPDATE jobs SET status = CASE status
                  WHEN 'created' THEN 'uploaded'
                  WHEN 'estimating' THEN 'uploaded'
                  WHEN 'awaiting_credit_reservation' THEN 'uploaded'
                  WHEN 'queued' THEN 'queued'
                  WHEN 'probing' THEN 'processing'
                  WHEN 'extracting_audio' THEN 'processing'
                  WHEN 'chunking' THEN 'processing'
                  WHEN 'transcribing' THEN 'processing'
                  WHEN 'generating_outputs' THEN 'processing'
                  WHEN 'qa_validating' THEN 'processing'
                  WHEN 'exporting' THEN 'processing'
                  WHEN 'complete' THEN 'completed'
                  WHEN 'failed' THEN 'failed'
                  WHEN 'cancelled' THEN 'cancelled'
                  ELSE 'processing'
                END
                WHERE status IN (
                  'created','estimating','awaiting_credit_reservation','queued','probing',
                  'extracting_audio','chunking','transcribing','generating_outputs',
                  'qa_validating','exporting','complete','failed','cancelled'
                )
                """
            )
        )
        op.execute(
            text(
                "ALTER TABLE jobs ALTER COLUMN status TYPE jobstatus USING (status::jobstatus)"
            )
        )
        return

    # Partial run: VARCHAR data but ``jobstatus`` type was dropped and not recreated.
    if data_type in ("character varying", "text") and enum_n == 0:
        op.execute(
            text(
                "CREATE TYPE jobstatus AS ENUM ("
                "'uploaded', 'queued', 'processing', 'completed', 'failed', 'cancelled')"
            )
        )
        op.execute(
            text(
                """
                UPDATE jobs SET status = CASE status
                  WHEN 'created' THEN 'uploaded'
                  WHEN 'estimating' THEN 'uploaded'
                  WHEN 'awaiting_credit_reservation' THEN 'uploaded'
                  WHEN 'queued' THEN 'queued'
                  WHEN 'probing' THEN 'processing'
                  WHEN 'extracting_audio' THEN 'processing'
                  WHEN 'chunking' THEN 'processing'
                  WHEN 'transcribing' THEN 'processing'
                  WHEN 'generating_outputs' THEN 'processing'
                  WHEN 'qa_validating' THEN 'processing'
                  WHEN 'exporting' THEN 'processing'
                  WHEN 'complete' THEN 'completed'
                  WHEN 'failed' THEN 'failed'
                  WHEN 'cancelled' THEN 'cancelled'
                  ELSE 'processing'
                END
                WHERE status IN (
                  'created','estimating','awaiting_credit_reservation','queued','probing',
                  'extracting_audio','chunking','transcribing','generating_outputs',
                  'qa_validating','exporting','complete','failed','cancelled'
                )
                """
            )
        )
        op.execute(
            text(
                "ALTER TABLE jobs ALTER COLUMN status TYPE jobstatus USING (status::jobstatus)"
            )
        )
        return

    # Slim enum exists but column is still VARCHAR (interrupted before final cast).
    if data_type in ("character varying", "text") and enum_n == 6:
        op.execute(
            text(
                "ALTER TABLE jobs ALTER COLUMN status TYPE jobstatus USING (status::jobstatus)"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _migrate_legacy_railway_jobstatus_enum(bind)

    cols_w = _cols(bind, "credit_wallets")
    if "balance_available" in cols_w and "processing_minutes_available" not in cols_w:
        op.alter_column(
            "credit_wallets",
            "balance_available",
            new_column_name="processing_minutes_available",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    cols_w = _cols(bind, "credit_wallets")
    if "balance_reserved" in cols_w and "processing_minutes_reserved" not in cols_w:
        op.alter_column(
            "credit_wallets",
            "balance_reserved",
            new_column_name="processing_minutes_reserved",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    cols_w = _cols(bind, "credit_wallets")
    if "balance_spent_lifetime" in cols_w and "processing_minutes_spent_lifetime" not in cols_w:
        op.alter_column(
            "credit_wallets",
            "balance_spent_lifetime",
            new_column_name="processing_minutes_spent_lifetime",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    cols_w = _cols(bind, "credit_wallets")
    if "balance_expired_lifetime" in cols_w and "processing_minutes_expired_lifetime" not in cols_w:
        op.alter_column(
            "credit_wallets",
            "balance_expired_lifetime",
            new_column_name="processing_minutes_expired_lifetime",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    cols_aa = _cols(bind, "annual_access")
    if "included_credits" in cols_aa and "included_processing_minutes_annual" not in cols_aa:
        op.alter_column(
            "annual_access",
            "included_credits",
            new_column_name="included_processing_minutes_annual",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    cols_j = _cols(bind, "jobs")
    if cols_j:
        if "estimated_credits" in cols_j and "estimated_processing_minutes" not in cols_j:
            op.alter_column(
                "jobs",
                "estimated_credits",
                new_column_name="estimated_processing_minutes",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
        cols_j = _cols(bind, "jobs")
        if "reserved_credits" in cols_j and "reserved_processing_minutes" not in cols_j:
            op.alter_column(
                "jobs",
                "reserved_credits",
                new_column_name="reserved_processing_minutes",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
        cols_j = _cols(bind, "jobs")
        if "actual_credits" in cols_j and "actual_processing_minutes_charged" not in cols_j:
            op.alter_column(
                "jobs",
                "actual_credits",
                new_column_name="actual_processing_minutes_charged",
                existing_type=sa.Integer(),
                existing_nullable=True,
            )
        cols_j = _cols(bind, "jobs")
        if "failure_reason" not in cols_j:
            op.add_column("jobs", sa.Column("failure_reason", sa.Text(), nullable=True))
        if "error_log_storage_key" not in cols_j:
            op.add_column("jobs", sa.Column("error_log_storage_key", sa.String(length=1024), nullable=True))
        if "media_kind" not in cols_j:
            op.add_column("jobs", sa.Column("media_kind", sa.String(length=64), nullable=True))
        if "source_content_type" not in cols_j:
            op.add_column("jobs", sa.Column("source_content_type", sa.String(length=255), nullable=True))

    cols_ma = _cols(bind, "media_assets")
    if cols_ma and "upload_content_type" not in cols_ma:
        op.add_column("media_assets", sa.Column("upload_content_type", sa.String(length=255), nullable=True))

    cols_ctx = _cols(bind, "credit_transactions")
    if "balance_after" in cols_ctx and "processing_minutes_available_after" not in cols_ctx:
        op.alter_column(
            "credit_transactions",
            "balance_after",
            new_column_name="processing_minutes_available_after",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    cols_ai = _cols(bind, "ai_usage_logs")
    if cols_ai and "credits_debited" in cols_ai and "processing_minutes_logged" not in cols_ai:
        op.alter_column(
            "ai_usage_logs",
            "credits_debited",
            new_column_name="processing_minutes_logged",
            existing_type=sa.Integer(),
            existing_nullable=True,
        )

    cols_jo = _cols(bind, "job_outputs")
    if cols_jo and "schema_version" not in cols_jo:
        op.add_column(
            "job_outputs",
            sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="1.0"),
        )
        op.alter_column("job_outputs", "schema_version", server_default=None)

    if "jobs" in inspect(bind).get_table_names():
        cols_jobs = _cols(bind, "jobs")
        if "failure_message" in cols_jobs and "failure_reason" in cols_jobs:
            op.execute(
                text(
                    """
                    UPDATE jobs SET failure_reason = failure_message
                    WHERE failure_reason IS NULL AND failure_message IS NOT NULL
                    """
                )
            )
        op.execute(
            text(
                """
                UPDATE jobs AS j
                SET media_kind = CAST(m.media_type AS TEXT)
                FROM media_assets AS m
                WHERE j.media_asset_id = m.id AND (j.media_kind IS NULL OR j.media_kind = '')
                """
            )
        )
        op.execute(
            text(
                """
                UPDATE jobs AS j
                SET source_content_type = m.upload_content_type
                FROM media_assets AS m
                WHERE j.media_asset_id = m.id AND j.source_content_type IS NULL
                  AND m.upload_content_type IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    # Irreversible enum/string normalization; column renames could be reversed in a follow-up if needed.
    pass
