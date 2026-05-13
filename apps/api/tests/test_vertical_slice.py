from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    CreditWallet,
    Job,
    JobOutput,
    JobOutputType,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    utcnow,
)
from app.settings import get_settings


def _bootstrap_org(session: Session, org_id: str, *, with_aa: bool = True, credits: int = 500):
    session.add(Organisation(id=org_id, name="Test Org", slug="demo-creator"))
    session.add(User(id="user_t", organisation_id=org_id, email="t@example.com"))
    if with_aa:
        now = utcnow()
        session.add(
            AnnualAccess(
                organisation_id=org_id,
                plan_code="creator_core",
                period_start=now,
                period_end=now + timedelta(days=365),
                hosting_until=now + timedelta(days=365),
                included_credits=credits,
            )
        )
    w = CreditWallet(organisation_id=org_id, balance_available=credits)
    session.add(w)
    session.commit()


def test_missing_annual_access_blocks_job(api_client, db_session: Session):
    _bootstrap_org(db_session, "org_no_aa", with_aa=False)
    r = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": "org_no_aa",
        },
        json={
            "media_asset_id": "missing",
            "requested_outputs": ["transcript"],
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("error") == "ACCESS_INACTIVE"


def test_insufficient_credits_blocks_job(api_client, db_session: Session):
    _bootstrap_org(db_session, "org_poor", credits=1)
    db_session.add(
        MediaAsset(
            organisation_id="org_poor",
            original_filename="a.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="orgs/org_poor/assets/ma_x/source/a.mp4",
            status=MediaAssetStatus.UPLOADED,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.organisation_id == "org_poor")).first()

    r = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": "org_poor",
        },
        json={
            "media_asset_id": ma.id,
            "requested_outputs": [
                "transcript",
                "chapters",
                "show_notes",
                "metadata",
                "ctas",
                "fact_sheet",
                "faqs",
                "hosted_manifest",
                "export_bundle",
            ],
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["error"] == "INSUFFICIENT_PROCESSING_TIME"
    assert detail["allowed"] is False


def test_job_creation_reserves_credits(api_client, db_session: Session):
    _bootstrap_org(db_session, "org_ok", credits=500)
    db_session.add(
        MediaAsset(
            organisation_id="org_ok",
            original_filename="a.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="orgs/org_ok/assets/ma1/source/a.mp4",
            status=MediaAssetStatus.UPLOADED,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.organisation_id == "org_ok")).first()

    r = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": "org_ok",
        },
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reserved_credits"] == body["estimated_credits"]
    job_id = body["job_id"]

    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == "org_ok")).one()
    assert wallet.balance_reserved >= body["reserved_credits"]

    job = db_session.get(Job, job_id)
    assert job.status == JobStatus.QUEUED


def test_manifest_endpoint_returns_payload(api_client, db_session: Session):
    org_id = "org_man"
    _bootstrap_org(db_session, org_id, credits=100)
    db_session.add(
        MediaAsset(
            id="ma_m",
            organisation_id=org_id,
            original_filename="x.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="k",
            status=MediaAssetStatus.UPLOADED,
            creator_slug="demo-creator",
            asset_slug="episode-001",
        )
    )
    db_session.add(
        Job(
            organisation_id=org_id,
            media_asset_id="ma_m",
            status=JobStatus.COMPLETE,
            requested_outputs_json=["hosted_manifest"],
        )
    )
    db_session.commit()
    job = db_session.exec(select(Job).where(Job.organisation_id == org_id)).first()
    db_session.add(
        JobOutput(
            job_id=job.id,
            organisation_id=org_id,
            output_type=JobOutputType.HOSTED_MANIFEST,
            json_payload={
                "schema_version": "1.0",
                "creator_slug": "demo-creator",
                "asset_slug": "episode-001",
                "canonical_title": "T",
                "summary": "S",
                "chapters": [],
                "topics": [],
                "facts": [],
                "faqs": [],
                "ctas": [],
                "links": {},
                "output_links": {"transcript": "https://example.invalid/transcript.json"},
            },
        )
    )
    db_session.commit()

    r = api_client.get("/v1/manifests/demo-creator/episode-001.json")
    assert r.status_code == 200
    data = r.json()
    assert data["canonical_title"] == "T"
    assert "output_links" in data


def test_media_duration_exceeds_max_blocks_job(api_client, db_session: Session, monkeypatch):
    monkeypatch.setenv("FF_MAX_MEDIA_SECONDS", "100")
    get_settings.cache_clear()
    try:
        _bootstrap_org(db_session, "org_long_media", credits=500)
        db_session.add(
            MediaAsset(
                organisation_id="org_long_media",
                original_filename="long.mp4",
                media_type=MediaType.VIDEO,
                storage_source_key="orgs/org_long_media/assets/ma_long/source/long.mp4",
                status=MediaAssetStatus.UPLOADED,
                duration_seconds=500.0,
            )
        )
        db_session.commit()
        ma = db_session.exec(select(MediaAsset).where(MediaAsset.organisation_id == "org_long_media")).first()
        r = api_client.post(
            "/v1/jobs",
            headers={
                "Authorization": "Bearer test-internal-key",
                "X-Org-Id": "org_long_media",
            },
            json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
        )
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail.get("error") == "MEDIA_DURATION_TOO_LONG"
    finally:
        get_settings.cache_clear()
