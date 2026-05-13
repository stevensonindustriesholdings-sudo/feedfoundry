"""Processing minutes reservation, goodwill, settlement, and job API."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.models import (
    AnnualAccess,
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    Job,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    utcnow,
)
from app.services.credit_ledger import (
    debit_reserved_credits,
    ledger_debit_key,
    ledger_goodwill_revoke_key,
    ledger_release_failure_key,
    ledger_reserve_key,
    release_reserved_credits,
    reserve_credits,
    revoke_goodwill_processing_minutes_on_job_failure,
)
from app.services.processing_time import reserve_processing_time_for_job
from app.settings import Settings, get_settings


def _bootstrap_org(session: Session, org_id: str, *, minutes: int):
    session.add(Organisation(id=org_id, name="T", slug=org_id))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"{org_id}@e.com"))
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


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_10_min_balance_5_min_file_no_goodwill(session: Session):
    org = "org_a"
    _bootstrap_org(session, org, minutes=10)
    session.add(
        MediaAsset(
            organisation_id=org,
            original_filename="a.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="k",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=300.0,
        )
    )
    session.commit()
    settings = Settings(ff_goodwill_max_shortfall_minutes=5, ff_goodwill_max_minutes_per_account_per_year=30)
    out = reserve_processing_time_for_job(
        session,
        organisation_id=org,
        job_id="job_x",
        estimated_minutes=5,
        settings=settings,
    )
    assert out.goodwill_minutes == 0
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_available == 5
    assert w.balance_reserved == 5


def test_3_min_balance_5_min_file_2_goodwill(session: Session):
    org = "org_b"
    _bootstrap_org(session, org, minutes=3)
    settings = Settings(ff_goodwill_max_shortfall_minutes=5, ff_goodwill_max_minutes_per_account_per_year=30)
    out = reserve_processing_time_for_job(
        session,
        organisation_id=org,
        job_id="job_y",
        estimated_minutes=5,
        settings=settings,
    )
    assert out.goodwill_minutes == 2
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_available == 0
    assert w.balance_reserved == 5
    gw = session.exec(
        select(CreditTransaction).where(CreditTransaction.type == CreditTransactionType.GOODWILL_GRANT)
    ).all()
    assert len(gw) == 1
    assert gw[0].amount == 2


def test_3_min_balance_12_min_file_blocked(session: Session):
    org = "org_c"
    _bootstrap_org(session, org, minutes=3)
    settings = Settings(ff_goodwill_max_shortfall_minutes=5, ff_goodwill_max_minutes_per_account_per_year=30)
    out = reserve_processing_time_for_job(
        session,
        organisation_id=org,
        job_id="job_z",
        estimated_minutes=12,
        settings=settings,
    )
    assert out.allowed is False
    assert out.shortfall_minutes == 9


def test_complete_job_consumes_minutes(session: Session):
    org = "org_d"
    _bootstrap_org(session, org, minutes=100)
    reserve_credits(
        session,
        organisation_id=org,
        job_id="job_done",
        amount=10,
        idempotency_key=ledger_reserve_key("job_done"),
    )
    session.commit()
    debit_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_done",
        amount=10,
        idempotency_key=ledger_debit_key("job_done"),
    )
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_reserved == 0
    assert w.balance_spent_lifetime == 10
    assert w.balance_available == 90


def test_fail_job_releases_reserve_revokes_goodwill(session: Session):
    org = "org_e"
    _bootstrap_org(session, org, minutes=3)
    settings = Settings(ff_goodwill_max_shortfall_minutes=5, ff_goodwill_max_minutes_per_account_per_year=30)
    reserve_processing_time_for_job(
        session,
        organisation_id=org,
        job_id="job_fail",
        estimated_minutes=5,
        settings=settings,
    )
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_reserved == 5
    assert w.balance_available == 0

    release_reserved_credits(
        session,
        organisation_id=org,
        job_id="job_fail",
        amount=5,
        idempotency_key=ledger_release_failure_key("job_fail"),
    )
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_reserved == 0
    assert w.balance_available == 5

    revoke_goodwill_processing_minutes_on_job_failure(
        session,
        organisation_id=org,
        job_id="job_fail",
        minutes=2,
        idempotency_key=ledger_goodwill_revoke_key("job_fail"),
    )
    session.commit()
    w = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org)).one()
    assert w.balance_available == 3
    assert w.balance_spent_lifetime == 0


def test_post_job_10_balance_5_min_no_warn(api_client: TestClient, db_session: Session):
    get_settings.cache_clear()
    org = "org_api1"
    _bootstrap_org(db_session, org, minutes=10)
    db_session.add(
        MediaAsset(
            organisation_id=org,
            original_filename="x.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="k1",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=300.0,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.storage_source_key == "k1")).one()
    r = api_client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org},
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estimated_minutes"] == 5
    assert body["warning"] is False
    get_settings.cache_clear()


def test_post_job_3_balance_5_min_goodwill(api_client: TestClient, db_session: Session):
    get_settings.cache_clear()
    org = "org_api2"
    _bootstrap_org(db_session, org, minutes=3)
    db_session.add(
        MediaAsset(
            organisation_id=org,
            original_filename="x.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="k2",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=300.0,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.storage_source_key == "k2")).one()
    r = api_client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org},
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["warning"] is True
    assert body["goodwill_minutes"] == 2
    job = db_session.get(Job, body["job_id"])
    assert job.goodwill_minutes_granted == 2
    get_settings.cache_clear()


def test_post_job_3_balance_12_min_blocked(api_client: TestClient, db_session: Session):
    get_settings.cache_clear()
    org = "org_api3"
    _bootstrap_org(db_session, org, minutes=3)
    db_session.add(
        MediaAsset(
            organisation_id=org,
            original_filename="big.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="k3",
            status=MediaAssetStatus.UPLOADED,
            duration_seconds=720.0,
        )
    )
    db_session.commit()
    ma = db_session.exec(select(MediaAsset).where(MediaAsset.storage_source_key == "k3")).one()
    r = api_client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org},
        json={"media_asset_id": ma.id, "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["error"] == "INSUFFICIENT_PROCESSING_TIME"
    assert d["shortfall_minutes"] == 9
    get_settings.cache_clear()
