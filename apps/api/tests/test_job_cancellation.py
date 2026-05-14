from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    Job,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    utcnow,
)

_HEADERS = {
    "Authorization": "Bearer test-internal-key",
    "X-Org-Id": "org_cancel",
}


def _bootstrap(session: Session, *, minutes: int = 500) -> MediaAsset:
    """Set up an org with annual access, a funded wallet, and one media asset."""
    org_id = "org_cancel"
    session.add(Organisation(id=org_id, name="Cancel Org", slug="cancel-creator"))
    session.add(User(id="user_cancel", organisation_id=org_id, email="c@example.com"))
    now = utcnow()
    session.add(
        AnnualAccess(
            organisation_id=org_id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_processing_minutes_annual=minutes,
        )
    )
    session.add(CreditWallet(organisation_id=org_id, processing_minutes_available=minutes))
    session.commit()
    session.add(
        MediaAsset(
            organisation_id=org_id,
            original_filename="a.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="orgs/org_cancel/assets/ma1/source/a.mp4",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=120.0,
        )
    )
    session.commit()
    ma = session.exec(select(MediaAsset).where(MediaAsset.organisation_id == org_id)).first()
    return ma


def _create_job(api_client, ma: MediaAsset) -> dict:
    r = api_client.post(
        "/v1/jobs",
        headers=_HEADERS,
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_cancel_reserved_job_releases_processing_minutes(api_client, db_session: Session):
    """Cancelling a reserved-but-not-charged job must return reserved minutes to available."""
    ma = _bootstrap(db_session, minutes=500)
    created = _create_job(api_client, ma)
    job_id = created["job_id"]
    reserved = int(created["reserved_processing_minutes"])
    assert reserved > 0

    # Wallet snapshot pre-cancel: minutes are reserved, not available.
    wallet_before = db_session.exec(
        select(CreditWallet).where(CreditWallet.organisation_id == "org_cancel")
    ).one()
    db_session.refresh(wallet_before)
    available_before = wallet_before.processing_minutes_available
    reserved_before = wallet_before.processing_minutes_reserved
    assert reserved_before >= reserved
    spent_before = wallet_before.processing_minutes_spent_lifetime

    r = api_client.post(f"/v1/jobs/{job_id}/cancel", headers=_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["reserved_processing_minutes"] == reserved

    # Wallet must show the reservation returned to available, no debit applied.
    wallet_after = db_session.exec(
        select(CreditWallet).where(CreditWallet.organisation_id == "org_cancel")
    ).one()
    db_session.refresh(wallet_after)
    assert wallet_after.processing_minutes_reserved == reserved_before - reserved
    assert wallet_after.processing_minutes_available == available_before + reserved
    assert wallet_after.processing_minutes_spent_lifetime == spent_before  # no debit

    # Ledger should record a RELEASE transaction tagged with the canonical idempotency key.
    txn = db_session.exec(
        select(CreditTransaction).where(
            CreditTransaction.idempotency_key == f"ff:job:{job_id}:cancel"
        )
    ).first()
    assert txn is not None
    assert txn.type == CreditTransactionType.RELEASE
    assert txn.amount == reserved

    # Job row must be in CANCELLED state.
    job = db_session.get(Job, job_id)
    assert job.status == JobStatus.CANCELLED


def test_cancel_is_idempotent_when_already_cancelled(api_client, db_session: Session):
    """A second cancel call must succeed (200) and not double-release minutes."""
    ma = _bootstrap(db_session, minutes=500)
    created = _create_job(api_client, ma)
    job_id = created["job_id"]

    r1 = api_client.post(f"/v1/jobs/{job_id}/cancel", headers=_HEADERS)
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "cancelled"

    wallet_after_first = db_session.exec(
        select(CreditWallet).where(CreditWallet.organisation_id == "org_cancel")
    ).one()
    db_session.refresh(wallet_after_first)
    available_snapshot = wallet_after_first.processing_minutes_available
    reserved_snapshot = wallet_after_first.processing_minutes_reserved

    r2 = api_client.post(f"/v1/jobs/{job_id}/cancel", headers=_HEADERS)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "cancelled"

    wallet_after_second = db_session.exec(
        select(CreditWallet).where(CreditWallet.organisation_id == "org_cancel")
    ).one()
    db_session.refresh(wallet_after_second)
    assert wallet_after_second.processing_minutes_available == available_snapshot
    assert wallet_after_second.processing_minutes_reserved == reserved_snapshot


def test_cancel_terminal_job_returns_409(api_client, db_session: Session):
    """Completed and failed jobs are terminal and cannot be cancelled."""
    ma = _bootstrap(db_session, minutes=500)
    created = _create_job(api_client, ma)
    completed_job_id = created["job_id"]

    job = db_session.get(Job, completed_job_id)
    job.status = JobStatus.COMPLETED
    db_session.add(job)
    db_session.commit()

    r = api_client.post(f"/v1/jobs/{completed_job_id}/cancel", headers=_HEADERS)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "job_already_terminal"
    assert "completed" in body["message"].lower()

    db_session.add(
        MediaAsset(
            organisation_id="org_cancel",
            original_filename="b.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="orgs/org_cancel/assets/ma2/source/b.mp4",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=120.0,
        )
    )
    db_session.commit()
    ma2 = db_session.exec(
        select(MediaAsset).where(
            MediaAsset.organisation_id == "org_cancel",
            MediaAsset.original_filename == "b.mp4",
        )
    ).one()
    created2 = _create_job(api_client, ma2)
    failed_job_id = created2["job_id"]

    failed = db_session.get(Job, failed_job_id)
    failed.status = JobStatus.FAILED
    db_session.add(failed)
    db_session.commit()

    r2 = api_client.post(f"/v1/jobs/{failed_job_id}/cancel", headers=_HEADERS)
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "job_already_terminal"


def test_cancel_unknown_job_returns_404(api_client, db_session: Session):
    """Cancelling an unknown id must return canonical 404 job_not_found."""
    _bootstrap(db_session, minutes=100)
    r = api_client.post("/v1/jobs/does-not-exist/cancel", headers=_HEADERS)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "job_not_found"
