"""Launch MVP intake routes (YouTube gated, playlist parent, upload shortcut)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.models import AnnualAccess, CreditWallet, Job, MediaAsset, Organisation, User, YoutubeSourceQueue, utcnow


def _bootstrap_org(session: Session, org_id: str, *, processing_minutes: int = 500):
    session.add(Organisation(id=org_id, name="Test Org", slug=f"slug-{org_id}"))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"{org_id}@example.com"))
    now = utcnow()
    session.add(
        AnnualAccess(
            organisation_id=org_id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_processing_minutes_annual=processing_minutes,
        )
    )
    session.add(CreditWallet(organisation_id=org_id, processing_minutes_available=processing_minutes))
    session.commit()


def test_intake_youtube_video_disabled(api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", raising=False)
    org_id = "org_intake_off"
    _bootstrap_org(db_session, org_id)
    r = api_client.post(
        "/v1/intake/youtube-video",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body.get("code") == "youtube_intake_disabled"


def test_intake_youtube_video_auth_required(api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", "1")
    org_id = "org_intake_auth"
    _bootstrap_org(db_session, org_id)
    r = api_client.post(
        "/v1/intake/youtube-video",
        headers={"X-Org-Id": org_id},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_intake_youtube_video_missing_org_returns_structured_404(api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", "1")
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_LIVE", "1")
    r = api_client.post(
        "/v1/intake/youtube-video",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": "org_missing_intake"},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 404, r.text
    body = r.json()
    assert body == {
        "code": "organisation_not_found",
        "message": "Organisation does not exist for this request.",
        "fields": ["X-Org-Id"],
    }
    assert db_session.exec(select(Job).where(Job.organisation_id == "org_missing_intake")).all() == []
    assert db_session.exec(select(YoutubeSourceQueue).where(YoutubeSourceQueue.organisation_id == "org_missing_intake")).all() == []


def test_intake_youtube_video_creates_stub_media_and_job(api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", "1")
    org_id = "org_intake_vid"
    _bootstrap_org(db_session, org_id)
    r = api_client.post(
        "/v1/intake/youtube-video",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_id"]
    assert data["queue_id"]
    assert data["status"] == "queued"
    assert data["acquisition_status"] == "queued_for_worker"
    assert data["live_acquisition_enabled"] is False
    ma = db_session.get(MediaAsset, data["media_asset_id"])
    assert ma is not None
    assert ma.intake_kind == "youtube_stub"
    assert ma.storage_source_key == f"ff-youtube-pending:{data['queue_id']}"
    q = db_session.get(YoutubeSourceQueue, data["queue_id"])
    assert q is not None
    assert q.job_id == data["job_id"]
    job = db_session.get(Job, data["job_id"])
    assert job is not None


def test_intake_youtube_video_schema_missing_returns_structured_503_without_debit(
    api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", "1")
    org_id = "org_intake_missing_schema"
    _bootstrap_org(db_session, org_id, processing_minutes=123)
    db_session.connection().execute(text("DROP TABLE youtube_source_queue"))
    db_session.commit()

    r = api_client.post(
        "/v1/intake/youtube-video",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "requested_outputs": ["transcript"]},
    )

    assert r.status_code == 503, r.text
    body = r.json()
    assert body["code"] == "youtube_intake_schema_unavailable"
    assert "youtube_source_queue" in body["message"]
    assert db_session.exec(select(Job).where(Job.organisation_id == org_id)).all() == []


def test_intake_youtube_playlist_parent_only(api_client, db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED", "1")
    org_id = "org_intake_pl"
    _bootstrap_org(db_session, org_id)
    r = api_client.post(
        "/v1/intake/youtube-playlist",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={"playlist_url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4GEHQulYEfZq7v3jXM"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "not_yet_expanded"
    rows = db_session.exec(select(YoutubeSourceQueue).where(YoutubeSourceQueue.id == data["queue_id"])).all()
    assert len(rows) == 1
    assert rows[0].job_id is None
    assert rows[0].media_asset_id is None


def test_intake_upload_matches_job_create(api_client, db_session: Session):
    org_id = "org_intake_upload"
    _bootstrap_org(db_session, org_id)
    pr = api_client.post(
        "/v1/uploads/presign",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={
            "filename": "clip.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 1_000_000,
            "media_type": "video",
        },
    )
    assert pr.status_code == 200
    media_asset_id = pr.json()["media_asset_id"]
    jr = api_client.post(
        "/v1/intake/upload",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
        json={"media_asset_id": media_asset_id, "requested_outputs": ["transcript"], "duration_seconds": 120},
    )
    assert jr.status_code == 200, jr.text
    ma = db_session.get(MediaAsset, media_asset_id)
    assert ma is not None
    assert ma.duration_seconds == 120.0
