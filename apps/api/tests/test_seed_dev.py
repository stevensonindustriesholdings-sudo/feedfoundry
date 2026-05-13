"""Seed script produces a usable dev org + wallet (run against sqlite fixture mirror)."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    Organisation,
    User,
    utcnow,
)


def test_seed_data_model_sqlite(db_session: Session):
    """Mirror scripts/seed_dev.py core inserts without subprocess."""
    now = utcnow()
    org = Organisation(
        id="org_dev_demo",
        name="FeedFoundry Dev Org",
        slug="demo-creator",
    )
    db_session.add(org)
    db_session.add(
        User(
            id="user_dev_demo",
            organisation_id=org.id,
            email="dev@feedfoundry.local",
        )
    )
    db_session.add(
        AnnualAccess(
            organisation_id=org.id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_processing_minutes_annual=300,
        )
    )
    w = CreditWallet(organisation_id=org.id, processing_minutes_available=300)
    db_session.add(w)
    db_session.flush()
    db_session.add(
        CreditTransaction(
            organisation_id=org.id,
            wallet_id=w.id,
            type=CreditTransactionType.ANNUAL_GRANT,
            amount=300,
            processing_minutes_available_after=300,
            memo="grant",
            idempotency_key="ff:seed_dev:annual_grant",
        )
    )
    db_session.commit()

    assert db_session.get(Organisation, "org_dev_demo").slug == "demo-creator"
    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
    assert wallet.processing_minutes_available == 300
