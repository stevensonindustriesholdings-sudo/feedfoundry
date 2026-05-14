"""Persistence smoke for Phase 7 ``AIRun`` / ``AIStageLog`` (offline sqlite)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    AIRun,
    AIStageLog,
    Job,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    utcnow,
)


def test_ai_run_and_stage_roundtrip(db_session: Session):
    org = Organisation(id="org_ai_test", name="AI Test Org", slug="ai-test-org")
    db_session.add(org)
    ma = MediaAsset(
        id="ma_ai_test",
        organisation_id=org.id,
        original_filename="x.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="k",
        status=MediaAssetStatus.UPLOADED,
    )
    db_session.add(ma)
    job = Job(
        id="job_ai_test",
        organisation_id=org.id,
        media_asset_id=ma.id,
        status=JobStatus.PROCESSING,
    )
    db_session.add(job)
    db_session.commit()

    run = AIRun(
        job_id=job.id,
        organisation_id=org.id,
        status="running",
        captain_plan_version="p7-0.1",
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    stage = AIStageLog(
        ai_run_id=run.id,
        job_id=job.id,
        stage_name="transcript_intelligence",
        status="completed",
        provider_name="mock",
        model_name="mock",
        started_at=utcnow(),
        finished_at=utcnow(),
        input_tokens=10,
        output_tokens=20,
        cost_estimate_internal=0.001,
        validation_status="passed",
        provider_request_id="mock-123",
        extra_json={"safe": True},
    )
    db_session.add(stage)
    db_session.commit()

    loaded = db_session.exec(select(AIStageLog).where(AIStageLog.ai_run_id == run.id)).all()
    assert len(loaded) == 1
    assert loaded[0].stage_name == "transcript_intelligence"
    assert loaded[0].cost_estimate_internal == 0.001
    assert loaded[0].validation_status == "passed"
