"""Launch MVP: media intake_kind + youtube_source_queue job/acquisition linkage.

Revision ID: 010_launch_mvp_intake_fields
Revises: 009_jobstatus_created_enum_label
Create Date: 2026-05-18

PostgreSQL upgrades existing deployments. SQLite test DBs use SQLModel.create_all().
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "010_launch_mvp_intake_fields"
down_revision: Union[str, None] = "009_jobstatus_created_enum_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


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

    ycols = _cols(bind, "youtube_source_queue")
    if not ycols:
        return

    if "queue_kind" not in ycols:
        op.add_column(
            "youtube_source_queue",
            sa.Column("queue_kind", sa.String(length=32), nullable=False, server_default="video"),
        )
    if "job_id" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("job_id", sa.String(), nullable=True))
        op.create_index("ix_youtube_source_queue_job_id", "youtube_source_queue", ["job_id"], unique=False)
        op.create_foreign_key(
            "fk_youtube_source_queue_job_id",
            "youtube_source_queue",
            "jobs",
            ["job_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "media_asset_id" not in ycols:
        op.add_column("youtube_source_queue", sa.Column("media_asset_id", sa.String(), nullable=True))
        op.create_foreign_key(
            "fk_youtube_source_queue_media_asset_id",
            "youtube_source_queue",
            "media_assets",
            ["media_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
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


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    ycols = _cols(bind, "youtube_source_queue")
    if ycols:
        for name, fk in (
            ("fk_youtube_source_queue_media_asset_id", "media_asset_id"),
            ("fk_youtube_source_queue_job_id", "job_id"),
        ):
            try:
                op.drop_constraint(name, "youtube_source_queue", type_="foreignkey")
            except Exception:
                pass
        for col in (
            "temp_media_storage_key",
            "source_duration_seconds",
            "source_title",
            "acquisition_error",
            "acquisition_status",
            "media_asset_id",
            "job_id",
            "queue_kind",
        ):
            if col in ycols:
                try:
                    op.drop_column("youtube_source_queue", col)
                except Exception:
                    pass
        try:
            op.drop_index("ix_youtube_source_queue_job_id", table_name="youtube_source_queue")
        except Exception:
            pass
    mcols = _cols(bind, "media_assets")
    if "intake_kind" in mcols:
        try:
            op.drop_column("media_assets", "intake_kind")
        except Exception:
            pass
