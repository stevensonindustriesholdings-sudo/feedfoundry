#!/usr/bin/env python3
"""
Bootstrap dev org, user, annual hosted-access entitlement, processing-allowance wallet, and demo media asset.

Usage (from repo root):
  export DATABASE_URL=postgresql+psycopg://...
  PYTHONPATH=apps/api python scripts/seed_dev.py
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlmodel import Session, create_engine, select  # noqa: E402

from app.models import (  # noqa: E402
    AnnualAccess,
    AnnualAccessStatus,
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    MediaAsset,
    MediaAssetStatus,
    MediaType,
    Organisation,
    User,
    UserRole,
    utcnow,
)

# Deterministic IDs for local curl / docs
ORG_ID = "org_dev_demo"
USER_ID = "user_dev_demo"
ASSET_ID = "ma_dev_demo"

# Matches creator_core annual included allowance from ai-routing.yaml (300 minutes)
STARTING_PROCESSING_MINUTES = 300


def seed() -> None:
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    if app_env in ("production", "prod"):
        allow = os.environ.get("ALLOW_DEV_SEED", "").strip().lower() in ("1", "true", "yes")
        if not allow:
            raise SystemExit(
                "Refusing to run seed_dev.py in production. "
                "Set ALLOW_DEV_SEED=true only for deliberate emergency bootstrap, then unset."
            )

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required")

    engine = create_engine(db_url, pool_pre_ping=True)
    now = utcnow()
    period_end = now + timedelta(days=365)

    with Session(engine) as session:
        org = session.get(Organisation, ORG_ID)
        if org is None:
            org = Organisation(
                id=ORG_ID,
                name="FeedFoundry Dev Org",
                slug="demo-creator",
            )
            session.add(org)
            session.flush()
        else:
            org.slug = org.slug or "demo-creator"
            session.add(org)

        user = session.get(User, USER_ID)
        if user is None:
            session.add(
                User(
                    id=USER_ID,
                    organisation_id=ORG_ID,
                    email="dev@feedfoundry.local",
                    role=UserRole.OWNER,
                )
            )
            org.owner_user_id = USER_ID
            session.add(org)

        aa = session.exec(
            select(AnnualAccess).where(AnnualAccess.organisation_id == ORG_ID)
        ).first()
        if aa is None:
            session.add(
                AnnualAccess(
                    organisation_id=ORG_ID,
                    plan_code="creator_core",
                    status=AnnualAccessStatus.ACTIVE,
                    period_start=now,
                    period_end=period_end,
                    hosting_until=period_end,
                    included_processing_minutes_annual=STARTING_PROCESSING_MINUTES,
                )
            )
        else:
            # Idempotent: bring existing row back to smoke-testable state without deleting history.
            if aa.status != AnnualAccessStatus.ACTIVE:
                aa.status = AnnualAccessStatus.ACTIVE
            aa.plan_code = aa.plan_code or "creator_core"
            if aa.period_end is None or aa.period_end < now:
                aa.period_end = period_end
            if aa.period_start is None:
                aa.period_start = now
            if aa.hosting_until is None or aa.hosting_until < now:
                aa.hosting_until = aa.period_end
            if aa.included_processing_minutes_annual < STARTING_PROCESSING_MINUTES:
                aa.included_processing_minutes_annual = STARTING_PROCESSING_MINUTES
            session.add(aa)

        wallet = session.exec(select(CreditWallet).where(CreditWallet.organisation_id == ORG_ID)).first()
        if wallet is None:
            wallet = CreditWallet(
                organisation_id=ORG_ID,
                processing_minutes_available=STARTING_PROCESSING_MINUTES,
                processing_minutes_reserved=0,
                processing_minutes_spent_lifetime=0,
            )
            session.add(wallet)
            session.flush()
            session.add(
                CreditTransaction(
                    organisation_id=ORG_ID,
                    wallet_id=wallet.id,
                    job_id=None,
                    type=CreditTransactionType.ANNUAL_GRANT,
                    amount=STARTING_PROCESSING_MINUTES,
                    processing_minutes_available_after=STARTING_PROCESSING_MINUTES,
                    memo="seed_dev annual hosted access processing allowance grant",
                    idempotency_key="ff:seed_dev:annual_grant",
                )
            )
        else:
            # Top up only if wallet empty and no prior seed grant (simple dev convenience)
            has_grant = session.exec(
                select(CreditTransaction).where(
                    CreditTransaction.idempotency_key == "ff:seed_dev:annual_grant"
                )
            ).first()
            if wallet.processing_minutes_available == 0 and not has_grant:
                wallet.processing_minutes_available = STARTING_PROCESSING_MINUTES
                session.add(wallet)
                session.flush()
                session.add(
                    CreditTransaction(
                        organisation_id=ORG_ID,
                        wallet_id=wallet.id,
                        job_id=None,
                        type=CreditTransactionType.ANNUAL_GRANT,
                        amount=STARTING_PROCESSING_MINUTES,
                        processing_minutes_available_after=STARTING_PROCESSING_MINUTES,
                        memo="seed_dev annual hosted access processing allowance grant",
                        idempotency_key="ff:seed_dev:annual_grant",
                    )
                )

        asset = session.get(MediaAsset, ASSET_ID)
        placeholder_key = f"orgs/{ORG_ID}/assets/{ASSET_ID}/source/placeholder.mp4"
        if asset is None:
            session.add(
                MediaAsset(
                    id=ASSET_ID,
                    organisation_id=ORG_ID,
                    uploaded_by_user_id=USER_ID,
                    original_filename="placeholder.mp4",
                    media_type=MediaType.VIDEO,
                    storage_source_key=placeholder_key,
                    status=MediaAssetStatus.UPLOADED,
                    creator_slug="demo-creator",
                    asset_slug="episode-001",
                    file_size_bytes=1024,
                )
            )

        session.commit()
        print("seed_ok")
        print(f"  organisation_id={ORG_ID} slug=demo-creator")
        print(f"  user_id={USER_ID}")
        print(f"  wallet_processing_minutes_available ~ {STARTING_PROCESSING_MINUTES} (after grant idempotency)")
        print(f"  demo_media_asset_id={ASSET_ID} manifest slugs demo-creator / episode-001")


if __name__ == "__main__":
    seed()
