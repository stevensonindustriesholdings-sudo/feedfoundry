"""Guarantee organisation row exists before child rows (FK), for smoke / staging only."""

from __future__ import annotations

from sqlmodel import Session

from app.models import Organisation
from app.settings import get_settings

_DEV_ORG_ID = "org_dev_demo"


def ensure_org_row_for_internal_routes(session: Session, organisation_id: str) -> None:
    """
    credit_wallets and media_assets FK to organisations.id.
    If the DB was partially seeded or drifted, inserts can 500 with IntegrityError.
    In non-production, auto-create the canonical dev org row only for org_dev_demo.
    """
    if session.get(Organisation, organisation_id) is not None:
        return
    env = (get_settings().app_env or "").strip().lower()
    if env in ("production", "prod"):
        return
    if organisation_id != _DEV_ORG_ID:
        return
    session.add(
        Organisation(
            id=_DEV_ORG_ID,
            name="FeedFoundry Dev Org",
            slug="demo-creator",
        )
    )
    session.flush()
