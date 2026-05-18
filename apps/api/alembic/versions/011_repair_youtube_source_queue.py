"""Repair missing YouTube source queue schema on live deployments.

Revision ID: 011_repair_youtube_source_queue
Revises: 010_launch_mvp_intake_fields
Create Date: 2026-05-18

Some early production deploys reached Alembic head without the
``youtube_source_queue`` table present. This forward-only repair migration is
idempotent: create the table when missing, otherwise add any launch-MVP columns
that are absent.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "011_repair_youtube_source_queue"
down_revision: Union[str, None] = "010_launch_mvp_intake_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(inspect(bind).get_table_names())


def _cols(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table)}


def _fk_names(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {fk["name"] for fk in insp.get_foreign_keys(table) if fk.get("name")}


def _create_youtube_source_queue() -> None:
    op.create_table(
        "youtube_source_queue",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.String(), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("youtube_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queue_kind", sa.String(length=32), nullable=False, server_default="video"),
        sa.Column("job_id", sa.String(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("media_asset_id", sa.String(), sa.ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acquisition_status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("acquisition_error", sa.Text(), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("source_duration_seconds", sa.Float(), nullable=True),
        sa.Column("temp_media_storage_key", sa.String(length=1024), nullable=True),
    )
    op.create_index("ix_youtube_queue_org_status", "youtube_source_queue", ["organisation_id", "status"])
    op.create_index("ix_youtube_source_queue_job_id", "youtube_source_queue", ["job_id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    mcols = _cols(bind, "media_assets")
    if mcols and "intake_kind" not in mcols:
        op.add_column(
            "media_assets",
            sa.Column("intake_kind", sa.String(length=32), nullable=False, server_default="upload"),
        )

    if "youtube_source_queue" not in _table_names(bind):
        _create_youtube_source_queue()
        return

    ycols = _cols(bind, "youtube_source_queue")
    if "queue_kind" not in ycols:
        op.add_column(
            "youtube_source_queue",
            sa.Column("queue_kind", sa.String(length=32), nullable=False, server_default="video"),
        )
    if "job_id" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("job_id", sa.String(), nullable=True))
    if "media_asset_id" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("media_asset_id", sa.String(), nullable=True))
    if "acquisition_status" not in ycols:
        op.add_column(
            "youtube_source_queue",
            sa.Column("acquisition_status", sa.String(length=64), nullable=False, server_default="pending"),
        )
    if "acquisition_error" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("acquisition_error", sa.Text(), nullable=True))
    if "source_title" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("source_title", sa.String(length=512), nullable=True))
    if "source_duration_seconds" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("source_duration_seconds", sa.Float(), nullable=True))
    if "temp_media_storage_key" not in ycols:
        op.add_column(
            "youtube_source_queue",
            sa.Column("temp_media_storage_key", sa.String(length=1024), nullable=True),
        )

    idxs = _index_names(bind, "youtube_source_queue")
    if "ix_youtube_queue_org_status" not in idxs:
        op.create_index("ix_youtube_queue_org_status", "youtube_source_queue", ["organisation_id", "status"])
    if "ix_youtube_source_queue_job_id" not in idxs:
        op.create_index("ix_youtube_source_queue_job_id", "youtube_source_queue", ["job_id"], unique=False)

    fks = _fk_names(bind, "youtube_source_queue")
    if "fk_youtube_source_queue_job_id" not in fks and "job_id" in _cols(bind, "youtube_source_queue"):
        op.create_foreign_key(
            "fk_youtube_source_queue_job_id",
            "youtube_source_queue",
            "jobs",
            ["job_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "fk_youtube_source_queue_media_asset_id" not in fks and "media_asset_id" in _cols(bind, "youtube_source_queue"):
        op.create_foreign_key(
            "fk_youtube_source_queue_media_asset_id",
            "youtube_source_queue",
            "media_assets",
            ["media_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Forward-only repair migration: do not drop repaired production schema.
    return
