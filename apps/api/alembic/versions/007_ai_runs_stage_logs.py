"""Add ai_runs and ai_stage_logs for Phase 7 orchestration persistence (internal/ops).

Revision ID: 007_ai_runs_stage_logs
Revises: 006_processing_minutes
Create Date: 2026-05-14

SQLite tests use SQLModel.create_all; Postgres uses this migration when present.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "007_ai_runs_stage_logs"
down_revision: Union[str, None] = "006_processing_minutes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "ai_runs" not in insp.get_table_names():
        op.create_table(
            "ai_runs",
            sa.Column("id", sa.String(length=48), primary_key=True),
            sa.Column("job_id", sa.String(length=48), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("organisation_id", sa.String(length=48), sa.ForeignKey("organisations.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
            sa.Column("captain_plan_version", sa.String(length=64), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.String(length=1024), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ai_runs_job_org", "ai_runs", ["job_id", "organisation_id"], unique=False)
    insp = inspect(bind)
    if "ai_stage_logs" not in insp.get_table_names():
        op.create_table(
            "ai_stage_logs",
            sa.Column("id", sa.String(length=48), primary_key=True),
            sa.Column("ai_run_id", sa.String(length=48), sa.ForeignKey("ai_runs.id"), nullable=False),
            sa.Column("job_id", sa.String(length=48), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("stage_name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("provider_name", sa.String(length=64), nullable=True),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_estimate_internal", sa.Float(), nullable=True),
            sa.Column("validation_status", sa.String(length=32), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.String(length=2048), nullable=True),
            sa.Column("provider_request_id", sa.String(length=128), nullable=True),
            sa.Column("extra_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ai_stage_logs_run", "ai_stage_logs", ["ai_run_id", "stage_name"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "ai_stage_logs" in insp.get_table_names():
        op.drop_index("ix_ai_stage_logs_run", table_name="ai_stage_logs")
        op.drop_table("ai_stage_logs")
    if "ai_runs" in insp.get_table_names():
        op.drop_index("ix_ai_runs_job_org", table_name="ai_runs")
        op.drop_table("ai_runs")
