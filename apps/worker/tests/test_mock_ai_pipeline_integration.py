"""Integration tests for optional mock AI enrichment (``FF_WORKER_MOCK_AI_ENRICHMENT``).

E worktree: merged ``phase7/agent-b-worker-ai-orchestrator`` at ``568c416`` (FF from integration
``a241b2e``) so tests import ``ai.pipeline``; no network; no credit ledger side effects.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.models import (
    AIRun,
    AIStageLog,
    Job,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def sqlite_engine():
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["FF_INTERNAL_API_KEY"] = "test-mock-ai-pipeline"
    os.environ["AI_ROUTING_CONFIG_PATH"] = str(REPO_ROOT / "ai-routing.yaml")
    from app.settings import get_settings

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    get_settings.cache_clear()


def _seed_job(session: Session, *, org_id: str, job_id: str, ma_id: str) -> Job:
    session.add(Organisation(id=org_id, name="AI Org", slug=f"slug-{org_id}"))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"u@{org_id}.test"))
    session.add(
        MediaAsset(
            id=ma_id,
            organisation_id=org_id,
            original_filename="f.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key=f"orgs/{org_id}/assets/{ma_id}/source/f.mp4",
            status=MediaAssetStatus.UPLOADED,
        )
    )
    job = Job(
        id=job_id,
        organisation_id=org_id,
        media_asset_id=ma_id,
        status=JobStatus.PROCESSING,
        reserved_processing_minutes=10,
        estimated_processing_minutes=10,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_flag_off_no_airun(monkeypatch, sqlite_engine):
    monkeypatch.delenv("FF_WORKER_MOCK_AI_ENRICHMENT", raising=False)
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_off", "job_ai_off", "ma_ai_off"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        maybe_run_mock_ai_job_enrichment(
            session,
            job,
            transcript_payload={"segments": [{"start": 0, "end": 1, "text": "hello world"}]},
            media_inspection_payload={"schema_version": "1.0", "duration_seconds": 2.0, "chunk_plan": []},
        )
        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert runs == []


def test_flag_on_persists_airun_and_stage_logs(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_MOCK_AI_ENRICHMENT", "1")
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_on", "job_ai_on", "ma_ai_on"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {
            "schema_version": "1.0",
            "duration_seconds": 5.0,
            "chunk_plan": [{"index": 0, "start_sec": 0.0, "end_sec": 2.5}],
        }
        tx = {"segments": [{"start": 0.0, "end": 5.0, "text": "alpha bravo charlie delta echo"}]}
        with patch("app.services.credit_ledger.debit_reserved_processing_minutes") as m_debit, patch(
            "app.services.credit_ledger.reserve_processing_minutes"
        ) as m_res, patch(
            "app.services.credit_ledger.release_reserved_processing_minutes"
        ) as m_rel:
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)
            m_debit.assert_not_called()
            m_res.assert_not_called()
            m_rel.assert_not_called()

        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        names = sorted(s.stage_name for s in stages)
        assert names == ["product_signal", "transcript_intelligence", "visual_analysis"]
        by_name = {s.stage_name: s for s in stages}
        assert by_name["transcript_intelligence"].status == "completed"
        assert by_name["transcript_intelligence"].validation_status == "accepted"
        assert by_name["visual_analysis"].status == "completed"
        assert by_name["product_signal"].status == "completed"


def test_validation_failure_writes_failed_stage_log(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_MOCK_AI_ENRICHMENT", "1")
    from ai.modules import visual_analysis as va_mod
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_val", "job_ai_val", "ma_ai_val"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {
            "schema_version": "1.0",
            "duration_seconds": 1.0,
            "chunk_plan": [{"index": 0, "start_sec": 0.0, "end_sec": 1.0}],
        }
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "some transcript"}]}

        def boom(*_a, **_k):
            raise va_mod.VisualAnalysisValidationError("forced failure for test")

        import ai.pipeline as pipeline_mod

        with patch.object(pipeline_mod, "run_visual_analysis", side_effect=boom):
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        vis = next(s for s in stages if s.stage_name == "visual_analysis")
        assert vis.status == "failed"
        assert vis.error_code == "visual_analysis_validation"
        assert "forced failure" in (vis.error_message or "")
        ti = next(s for s in stages if s.stage_name == "transcript_intelligence")
        assert ti.status == "completed"


def test_cancellation_stops_pending_stages(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_MOCK_AI_ENRICHMENT", "1")
    from ai import pipeline as pipeline_mod
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    calls = {"n": 0}

    def cancel_after_transcript(*a, **k):
        calls["n"] += 1
        # 1: initial, 2: before TI run, 3: after TI — before visual
        return calls["n"] >= 4

    org_id, job_id, ma_id = "org_ai_can", "job_ai_can", "ma_ai_can"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {
            "schema_version": "1.0",
            "duration_seconds": 3.0,
            "chunk_plan": [{"index": 0, "start_sec": 0.0, "end_sec": 1.5}],
        }
        tx = {"segments": [{"start": 0.0, "end": 3.0, "text": "one two three four five"}]}
        with patch.object(pipeline_mod, "_job_is_cancelled", side_effect=cancel_after_transcript):
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        run = session.exec(select(AIRun).where(AIRun.job_id == job_id)).one()
        assert run.status == "cancelled"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == run.id)).all()
        names = {s.stage_name for s in stages}
        assert "transcript_intelligence" in names
        assert "visual_analysis" not in names
        assert "product_signal" not in names

