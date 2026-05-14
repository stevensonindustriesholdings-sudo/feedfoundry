"""Integration tests for optional mock AI enrichment (``FF_WORKER_AI_ENRICHMENT_ENABLED``).

Merged ``phase7/agent-b-worker-ai-orchestrator`` for ``ai.pipeline``; no network;
no credit ledger side effects.
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
    monkeypatch.delenv("FF_WORKER_AI_ENRICHMENT_ENABLED", raising=False)
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


def test_flag_on_persists_airun_transcript_validates_skips_visual_and_product(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
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
        maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        names = sorted(s.stage_name for s in stages)
        assert names == ["product_signal", "transcript_intelligence", "visual_analysis"]
        by_name = {s.stage_name: s for s in stages}
        assert by_name["transcript_intelligence"].status == "completed"
        assert by_name["transcript_intelligence"].validation_status == "accepted"
        ex = by_name["transcript_intelligence"].extra_json or {}
        assert ex.get("artifact_count", 0) >= 1
        assert "artifact_digest" in ex
        assert by_name["visual_analysis"].status == "skipped"
        assert by_name["visual_analysis"].error_message == "no_visual_inputs"
        assert by_name["product_signal"].status == "skipped"
        assert by_name["product_signal"].error_message == "no_product_images"


def test_enrichment_openai_live_no_key_falls_back_mock_no_http(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE", "1")
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_nk", "job_ai_nk", "ma_ai_nk"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {"schema_version": "1.0", "duration_seconds": 1.0, "chunk_plan": []}
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "offline enrichment openai flag but no key"}]}
        with patch("httpx.Client.post") as m_post:
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)
            m_post.assert_not_called()
        ti = session.exec(
            select(AIStageLog).where(AIStageLog.job_id == job_id, AIStageLog.stage_name == "transcript_intelligence")
        ).one()
        assert ti.provider_name == "mock"


def test_no_credit_ledger_calls_during_enrichment(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_led", "job_ai_led", "ma_ai_led"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {"schema_version": "1.0", "duration_seconds": 1.0, "chunk_plan": []}
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "ledger isolation text here"}]}
        with patch("app.services.credit_ledger.debit_reserved_processing_minutes") as m_debit, patch(
            "app.services.credit_ledger.reserve_processing_minutes"
        ) as m_res, patch(
            "app.services.credit_ledger.release_reserved_processing_minutes"
        ) as m_rel:
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)
            m_debit.assert_not_called()
            m_res.assert_not_called()
            m_rel.assert_not_called()


def test_transcript_intelligence_validation_failure_logs_failed_stage(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai.modules import transcript_intelligence as ti_mod
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_ti", "job_ai_ti", "ma_ai_ti"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {"schema_version": "1.0", "duration_seconds": 1.0, "chunk_plan": []}
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "some transcript"}]}

        def boom(*_a, **_k):
            raise ti_mod.TranscriptIntelligenceValidationError("forced TI failure for test")

        import ai.pipeline as pipeline_mod

        with patch.object(pipeline_mod, "run_transcript_intelligence", side_effect=boom):
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        ti = next(s for s in stages if s.stage_name == "transcript_intelligence")
        assert ti.status == "failed"
        assert ti.error_code == "transcript_intelligence_validation"


def test_visual_analysis_validation_failure_logs_failed_stage(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai.modules import visual_analysis as va_mod
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_va", "job_ai_va", "ma_ai_va"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {
            "schema_version": "1.0",
            "duration_seconds": 1.0,
            "chunk_plan": [],
            "keyframes": [{"frame_id": "kf-test", "t_ms": 0}],
        }
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "some transcript"}]}

        def boom(*_a, **_k):
            raise va_mod.VisualAnalysisValidationError("forced visual failure for test")

        import ai.pipeline as pipeline_mod

        with patch.object(pipeline_mod, "run_visual_analysis", side_effect=boom):
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        runs = session.exec(select(AIRun).where(AIRun.job_id == job_id)).all()
        assert len(runs) == 1
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == runs[0].id)).all()
        vis = next(s for s in stages if s.stage_name == "visual_analysis")
        assert vis.status == "failed"
        assert vis.error_code == "visual_analysis_validation"
        assert "forced visual" in (vis.error_message or "")


def test_cancellation_stops_before_visual_analysis(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai import pipeline as pipeline_mod
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    calls = {"n": 0}

    def cancel_before_visual(*_a, **_k):
        calls["n"] += 1
        return calls["n"] >= 4

    org_id, job_id, ma_id = "org_ai_can", "job_ai_can", "ma_ai_can"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {
            "schema_version": "1.0",
            "duration_seconds": 3.0,
            "chunk_plan": [],
            "keyframes": [{"frame_id": "kf-can", "t_ms": 0}],
        }
        tx = {"segments": [{"start": 0.0, "end": 3.0, "text": "one two three four five"}]}
        with patch.object(pipeline_mod, "_job_is_cancelled", side_effect=cancel_before_visual):
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)

        run = session.exec(select(AIRun).where(AIRun.job_id == job_id)).one()
        assert run.status == "cancelled"
        stages = session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == run.id)).all()
        names = {s.stage_name for s in stages}
        assert "transcript_intelligence" in names
        assert "visual_analysis" not in names
        assert "product_signal" not in names


def test_enabled_no_rows_when_no_transcript_and_no_optional_inputs(monkeypatch, sqlite_engine):
    """Enrichment on but nothing to run: no AIRun (same as idle enrichment)."""
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_empty", "job_ai_empty", "ma_ai_empty"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {"schema_version": "1.0", "duration_seconds": 2.0, "chunk_plan": []}
        maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=None, media_inspection_payload=mi)
        assert session.exec(select(AIRun).where(AIRun.job_id == job_id)).all() == []


def test_no_http_client_used_by_enrichment_path(monkeypatch, sqlite_engine):
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_ENABLED", "1")
    from ai.pipeline import maybe_run_mock_ai_job_enrichment

    org_id, job_id, ma_id = "org_ai_http", "job_ai_http", "ma_ai_http"
    with Session(sqlite_engine) as session:
        job = _seed_job(session, org_id=org_id, job_id=job_id, ma_id=ma_id)
        mi = {"schema_version": "1.0", "duration_seconds": 1.0, "chunk_plan": []}
        tx = {"segments": [{"start": 0.0, "end": 1.0, "text": "offline enrichment"}]}
        with patch("httpx.Client.post") as m_post:
            maybe_run_mock_ai_job_enrichment(session, job, transcript_payload=tx, media_inspection_payload=mi)
            m_post.assert_not_called()
