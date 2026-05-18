"""Internal admin route for optional ``agent_bundle.json`` read-through."""

from __future__ import annotations

import pytest

from app.models import Job, JobOutput, JobOutputType, JobStatus, MediaAsset, MediaType, Organisation
from app.services import storage as storage_service


@pytest.fixture(autouse=True)
def _clear_agent_bundle_admin_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FF_AGENT_BUNDLE_ADMIN_API_ENABLED", raising=False)
    yield


def test_admin_agent_bundle_404_when_env_flag_off(api_client) -> None:
    r = api_client.get(
        "/v1/admin/jobs/job_missing/agent-bundle",
        headers={"Authorization": "Bearer test-internal-key"},
    )
    assert r.status_code == 404
    assert r.json().get("code") == "not_found"


def test_admin_agent_bundle_json_ok(api_client, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FF_AGENT_BUNDLE_ADMIN_API_ENABLED", "1")
    monkeypatch.setattr(storage_service, "storage_client_ready", lambda settings=None: True)
    monkeypatch.setattr(storage_service, "bucket_for_outputs", lambda settings=None: "outputs-bucket")
    monkeypatch.setattr(
        storage_service,
        "get_object_bytes",
        lambda **kwargs: b'{"execution_mode": "deterministic_mock"}',
    )

    org = Organisation(name="Org AB")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    ma = MediaAsset(
        organisation_id=org.id,
        original_filename="demo.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="orgs/%s/assets/%s/source/demo.mp4" % (org.id, "ma_ab"),
    )
    db_session.add(ma)
    db_session.commit()
    db_session.refresh(ma)

    job = Job(organisation_id=org.id, media_asset_id=ma.id, status=JobStatus.COMPLETED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    db_session.add(
        JobOutput(
            job_id=job.id,
            organisation_id=org.id,
            output_type=JobOutputType.AGENT_BUNDLE,
            storage_key=f"orgs/{org.id}/jobs/{job.id}/outputs/agent_bundle.json",
        )
    )
    db_session.commit()

    r = api_client.get(
        f"/v1/admin/jobs/{job.id}/agent-bundle",
        headers={"Authorization": "Bearer test-internal-key"},
    )
    assert r.status_code == 200
    assert r.json() == {"execution_mode": "deterministic_mock"}


def test_admin_agent_bundle_404_without_output_row(api_client, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FF_AGENT_BUNDLE_ADMIN_API_ENABLED", "1")
    monkeypatch.setattr(storage_service, "storage_client_ready", lambda settings=None: True)

    org = Organisation(name="Org AB2")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    ma = MediaAsset(
        organisation_id=org.id,
        original_filename="demo.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="sk",
    )
    db_session.add(ma)
    db_session.commit()
    db_session.refresh(ma)

    job = Job(organisation_id=org.id, media_asset_id=ma.id, status=JobStatus.COMPLETED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    r = api_client.get(
        f"/v1/admin/jobs/{job.id}/agent-bundle",
        headers={"Authorization": "Bearer test-internal-key"},
    )
    assert r.status_code == 404
