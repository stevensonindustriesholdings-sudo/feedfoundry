"""Cross-organisation isolation for jobs and outputs (internal-key + X-Org-Id MVP)."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    CreditWallet,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    utcnow,
)


def _bootstrap_org(session: Session, org_id: str, *, minutes: int = 500) -> None:
    session.add(Organisation(id=org_id, name=f"Org {org_id}", slug=org_id))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"{org_id}@example.com"))
    now = utcnow()
    session.add(
        AnnualAccess(
            organisation_id=org_id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_credits=minutes,
        )
    )
    session.add(CreditWallet(organisation_id=org_id, balance_available=minutes))
    session.commit()


def test_org_b_cannot_fetch_org_a_job(api_client, db_session: Session):
    org_a = "org_iso_a"
    org_b = "org_iso_b"
    _bootstrap_org(db_session, org_a)
    _bootstrap_org(db_session, org_b)
    db_session.add(
        MediaAsset(
            organisation_id=org_a,
            original_filename="a.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="orgs/org_iso_a/assets/ma_iso/source/a.mp4",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=120.0,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.organisation_id == org_a)).first()

    r_create = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_a,
        },
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r_create.status_code == 200
    job_id = r_create.json()["job_id"]

    r_b = api_client.get(
        f"/v1/jobs/{job_id}",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_b,
        },
    )
    assert r_b.status_code == 404

    r_out = api_client.get(
        f"/v1/jobs/{job_id}/outputs",
        headers={
            "Authorization": "Bearer test-internal-key",
            "X-Org-Id": org_b,
        },
    )
    assert r_out.status_code == 404
