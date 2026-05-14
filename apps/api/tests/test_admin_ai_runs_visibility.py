"""Internal admin AI run visibility — auth, scoping, redaction."""

from __future__ import annotations

from fastapi.testclient import TestClient
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

HDR = {"Authorization": "Bearer test-internal-key"}


def _seed_org_job_run(db_session: Session) -> tuple[str, str, str]:
    org = Organisation(id="org_vis_admin", name="Vis Org", slug="vis-org")
    db_session.add(org)
    ma = MediaAsset(
        id="ma_vis_admin",
        organisation_id=org.id,
        original_filename="clip.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="k-vis",
        status=MediaAssetStatus.UPLOADED,
    )
    db_session.add(ma)
    job = Job(
        id="job_vis_admin",
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
        captain_plan_version="p7-vis",
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    s1 = AIStageLog(
        ai_run_id=run.id,
        job_id=job.id,
        stage_name="stage_a",
        status="completed",
        provider_name="mock",
        model_name="mock-1",
        input_tokens=3,
        output_tokens=4,
        cost_estimate_internal=0.01,
        validation_status="passed",
        extra_json={"prompt": "secret", "nested": {"key": "x"}},
    )
    s2 = AIStageLog(
        ai_run_id=run.id,
        job_id=job.id,
        stage_name="stage_b",
        status="completed",
        provider_name="openai",
        model_name="gpt-test",
        validation_status="passed",
        extra_json={"foo": "bar"},
    )
    db_session.add(s1)
    db_session.add(s2)
    db_session.commit()
    return org.id, job.id, run.id


def test_admin_ai_runs_requires_internal_key(api_client: TestClient):
    r = api_client.get("/v1/admin/ai-runs")
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "unauthorized"
    assert body["fields"] == []


def test_admin_ai_runs_list_filter_and_redaction(api_client: TestClient, db_session: Session):
    org_id, job_id, run_id = _seed_org_job_run(db_session)

    r = api_client.get("/v1/admin/ai-runs", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert "ai_runs" in body and "count" in body
    assert body["count"] >= 1

    r_org = api_client.get(
        "/v1/admin/ai-runs",
        headers=HDR,
        params={"organisation_id": org_id},
    )
    assert r_org.status_code == 200
    data = r_org.json()
    assert data["count"] >= 1
    run = next(x for x in data["ai_runs"] if x["id"] == run_id)
    assert run["job_id"] == job_id
    assert run["organisation_id"] == org_id
    assert run["provider_mode"] == "mixed"
    assert run["stage_count"] == 2
    stages = run["stages"]
    assert len(stages) == 2
    for st in stages:
        assert "extra_json" not in st
        assert "prompt" not in st
        assert "cost_estimate_internal" in st
        assert "validation_status" in st

    r_job = api_client.get(
        "/v1/admin/ai-runs",
        headers=HDR,
        params={"job_id": job_id},
    )
    assert r_job.status_code == 200
    assert any(x["id"] == run_id for x in r_job.json()["ai_runs"])


def test_admin_ai_run_detail_not_found(api_client: TestClient):
    r = api_client.get("/v1/admin/ai-runs/air_nonexistent", headers=HDR)
    assert r.status_code == 404
    err = r.json()
    assert err["code"] == "not_found"
    assert err["fields"] == []


def test_admin_ai_run_detail_ok(api_client: TestClient, db_session: Session):
    _org_id, _job_id, run_id = _seed_org_job_run(db_session)
    r = api_client.get(f"/v1/admin/ai-runs/{run_id}", headers=HDR)
    assert r.status_code == 200
    row = r.json()
    assert row["id"] == run_id
    assert row["stage_count"] == 2
    assert all("extra_json" not in s for s in row["stages"])


def test_admin_job_ai_runs_org_scope(api_client: TestClient, db_session: Session):
    org_id, job_id, run_id = _seed_org_job_run(db_session)

    r_ok = api_client.get(f"/v1/admin/jobs/{job_id}/ai-runs", headers=HDR)
    assert r_ok.status_code == 200
    assert r_ok.json()["count"] == 1
    assert r_ok.json()["ai_runs"][0]["id"] == run_id

    r_scoped = api_client.get(
        f"/v1/admin/jobs/{job_id}/ai-runs",
        headers=HDR,
        params={"organisation_id": org_id},
    )
    assert r_scoped.status_code == 200
    assert r_scoped.json()["count"] == 1

    r_wrong_org = api_client.get(
        f"/v1/admin/jobs/{job_id}/ai-runs",
        headers=HDR,
        params={"organisation_id": "org_other"},
    )
    assert r_wrong_org.status_code == 404
    assert r_wrong_org.json()["code"] == "job_not_found"

    r_bad_job = api_client.get("/v1/admin/jobs/job_nope/ai-runs", headers=HDR)
    assert r_bad_job.status_code == 404
    assert r_bad_job.json()["code"] == "job_not_found"


def test_admin_job_ai_runs_empty(api_client: TestClient, db_session: Session):
    org = Organisation(id="org_empty_runs", name="E", slug="e")
    db_session.add(org)
    ma = MediaAsset(
        id="ma_empty_runs",
        organisation_id=org.id,
        original_filename="a.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="k2",
        status=MediaAssetStatus.UPLOADED,
    )
    db_session.add(ma)
    job = Job(
        id="job_empty_runs",
        organisation_id=org.id,
        media_asset_id=ma.id,
        status=JobStatus.PROCESSING,
    )
    db_session.add(job)
    db_session.commit()

    r = api_client.get("/v1/admin/jobs/job_empty_runs/ai-runs", headers=HDR)
    assert r.status_code == 200
    assert r.json() == {"ai_runs": [], "count": 0}

    # DB still has job
    assert db_session.get(Job, "job_empty_runs") is not None
    loaded = db_session.exec(select(AIRun).where(AIRun.job_id == "job_empty_runs")).all()
    assert loaded == []
