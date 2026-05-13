"""Upload presign → job creation → job read (product slice, no real R2)."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    CreditWallet,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    utcnow,
)


def _bootstrap_org(session: Session, org_id: str, *, credits: int = 500):
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
            included_credits=credits,
        )
    )
    session.add(CreditWallet(organisation_id=org_id, balance_available=credits))
    session.commit()


def test_presign_then_job_then_get_job(api_client, db_session: Session):
    org_id = "org_upload_flow"
    _bootstrap_org(db_session, org_id, credits=500)

    pr = api_client.post(
        "/v1/uploads/presign",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_id,
        },
        json={
            "filename": "episode.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 2_048_000,
            "media_type": "video",
        },
    )
    assert pr.status_code == 200, pr.text
    presign_body = pr.json()
    media_asset_id = presign_body["media_asset_id"]
    assert media_asset_id
    assert "upload_url" in presign_body
    assert presign_body["storage_key"].startswith(f"orgs/{org_id}/assets/{media_asset_id}/source/")

    ma = db_session.get(MediaAsset, media_asset_id)
    assert ma is not None
    assert ma.status == MediaAssetStatus.UPLOADED
    assert ma.storage_source_key.startswith(f"orgs/{org_id}/assets/{media_asset_id}/source/")

    jr = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_id,
        },
        json={"media_asset_id": media_asset_id, "requested_outputs": ["transcript", "chapters"]},
    )
    assert jr.status_code == 200, jr.text
    job_body = jr.json()
    job_id = job_body["job_id"]
    assert job_body["status"] == JobStatus.QUEUED.value
    assert job_body["reserved_credits"] == job_body["estimated_credits"]

    gr = api_client.get(
        f"/v1/jobs/{job_id}",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_id,
        },
    )
    assert gr.status_code == 200
    assert gr.json()["status"] == JobStatus.QUEUED.value
    assert gr.json()["job_id"] == job_id

    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org_id)).one()
    assert wallet.balance_reserved >= job_body["reserved_credits"]


def test_presign_rejects_without_annual_access(api_client, db_session: Session):
    org_id = "org_presign_no_aa"
    session = db_session
    session.add(Organisation(id=org_id, name="No AA", slug="no-aa-slug"))
    session.add(User(id="user_naa", organisation_id=org_id, email="naa@example.com"))
    session.add(CreditWallet(organisation_id=org_id, balance_available=50))
    session.commit()

    pr = api_client.post(
        "/v1/uploads/presign",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_id,
        },
        json={
            "filename": "a.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 1000,
            "media_type": "video",
        },
    )
    assert pr.status_code == 403
    assert pr.json()["detail"] == "annual_access_required"
