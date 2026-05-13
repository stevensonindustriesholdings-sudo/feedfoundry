"""Worker credit settlement mirrors production: success debits reserved; failure releases without debit."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.models import (
    Job,
    JobStatus,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
)
from app.services.credit_ledger import get_or_create_wallet, ledger_reserve_key, reserve_credits

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def sqlite_engine():
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["FF_INTERNAL_API_KEY"] = "test-worker-ledger-key"
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


def _seed_org_job_reserved(session: Session, *, org_id: str, job_id: str, ma_id: str, reserve_amount: int):
    session.add(Organisation(id=org_id, name="Ledger Org", slug=f"slug-{org_id}"))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"u@{org_id}.test"))
    w = get_or_create_wallet(session, org_id)
    w.balance_available = 500
    session.add(w)
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
    session.add(
        Job(
            id=job_id,
            organisation_id=org_id,
            media_asset_id=ma_id,
            status=JobStatus.EXPORTING,
            estimated_credits=reserve_amount,
            reserved_credits=reserve_amount,
        )
    )
    session.commit()
    reserve_credits(
        session,
        organisation_id=org_id,
        job_id=job_id,
        amount=reserve_amount,
        idempotency_key=ledger_reserve_key(job_id),
    )
    session.commit()


def test_settle_credits_debits_processing_allowance(sqlite_engine):
    """Successful settlement debits reserved credits (product uses credits as processing allowance)."""
    import worker as worker_mod

    org_id = "org_settle_ok"
    job_id = "job_settle_ok"
    ma_id = "ma_settle_ok"

    with Session(sqlite_engine) as session:
        _seed_org_job_reserved(session, org_id=org_id, job_id=job_id, ma_id=ma_id, reserve_amount=55)
        job = session.get(Job, job_id)
        assert job is not None
        worker_mod._settle_credits(session, job)
        session.refresh(job)
        assert job.actual_credits == 55

        w = get_or_create_wallet(session, org_id)
        session.refresh(w)
        assert w.balance_reserved == 0
        assert w.balance_spent_lifetime == 55
        assert w.balance_available == 500 - 55


def test_fail_job_releases_reserve_without_debit(sqlite_engine):
    """Failed processing must not debit lifetime spend; reservation returns to available."""
    import worker as worker_mod

    org_id = "org_fail_rel"
    job_id = "job_fail_rel"
    ma_id = "ma_fail_rel"

    with Session(sqlite_engine) as session:
        _seed_org_job_reserved(session, org_id=org_id, job_id=job_id, ma_id=ma_id, reserve_amount=42)
        job = session.get(Job, job_id)
        assert job is not None
        worker_mod.fail_job(session, job, "ffmpeg_error", "simulated failure")

        job2 = session.get(Job, job_id)
        assert job2.status == JobStatus.FAILED
        assert job2.failure_code == "ffmpeg_error"

        w = get_or_create_wallet(session, org_id)
        session.refresh(w)
        assert w.balance_reserved == 0
        assert w.balance_spent_lifetime == 0
        assert w.balance_available == 500
