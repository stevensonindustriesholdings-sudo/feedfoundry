#!/usr/bin/env python3
"""
Idempotent staging/dev credit top-up for org_dev_demo (sample-pack / real-media smoke).

**Never** run with ``APP_ENV=production`` or ``APP_ENV=prod``.

Uses existing ledger ``purchase_credits_from_stripe`` with a fixed idempotency key so the
operation is safe to retry and does not duplicate grants.

Environment:
  DATABASE_URL — required (same Postgres as API / worker; not printed by this script)
  APP_ENV — must be ``staging``, ``development``, or ``dev`` (unset is treated as ``development``)
  STAGING_SMOKE_TOPUP_ORG_ID — default ``org_dev_demo``
  STAGING_SMOKE_TOPUP_CREDITS — default ``10000`` (whole processing minutes; legacy env name)
  STAGING_SMOKE_TOPUP_IDEMPOTENCY_KEY — default ``ff:smoke:sample_pack_topup:v1``

Usage (from repo root, after ``export DATABASE_URL=...`` and ``export APP_ENV=staging``):

  PYTHONPATH=apps/api python3 tools/grant_staging_smoke_credits.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))

from sqlmodel import Session, create_engine  # noqa: E402

from app.models import Organisation  # noqa: E402
from app.services.credit_ledger import get_or_create_wallet, purchase_credits_from_stripe  # noqa: E402


def _allowed_app_env(raw: str) -> bool:
    e = (raw or "development").strip().lower()
    if e in ("production", "prod"):
        return False
    return True


def _normalize_app_env(raw: str) -> str:
    return (raw or "development").strip().lower()


def main() -> int:
    raw_env = os.environ.get("APP_ENV", "")
    if not _allowed_app_env(raw_env):
        print("Refusing: APP_ENV is production or prod.", file=sys.stderr)
        return 1
    app_env = _normalize_app_env(raw_env)
    if app_env not in ("development", "dev", "staging"):
        print(
            f"Refusing: APP_ENV must be development, dev, or staging (got {app_env!r}).",
            file=sys.stderr,
        )
        return 1

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 2

    org_id = os.environ.get("STAGING_SMOKE_TOPUP_ORG_ID", "org_dev_demo").strip()
    credits = int(os.environ.get("STAGING_SMOKE_TOPUP_CREDITS", "10000"))
    idem = os.environ.get("STAGING_SMOKE_TOPUP_IDEMPOTENCY_KEY", "ff:smoke:sample_pack_topup:v1").strip()

    engine = create_engine(db_url, pool_pre_ping=True)
    with Session(engine) as session:
        org = session.get(Organisation, org_id)
        if org is None:
            print(f"Organisation not found: {org_id} (seed the org first).", file=sys.stderr)
            return 1
        get_or_create_wallet(session, org_id)
        session.commit()

        snap = purchase_credits_from_stripe(
            session,
            organisation_id=org_id,
            credits=credits,
            idempotency_key=idem,
            stripe_reference=None,
            memo="staging_smoke_sample_pack_topup",
        )
        session.commit()

    print(f"OK organisation={org_id} processing_minutes_available={snap.processing_minutes_available}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
