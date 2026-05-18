"""Guarantee organisation row exists before child rows (FK), for smoke / staging only."""

from __future__ import annotations

from sqlmodel import Session

from app.models import Organisation
from app.settings import get_settings

_DEV_ORG_ID = "org_dev_demo"


class OrganisationNotFound(LookupError):
    """Raised when a request references an organisation that is not present."""


def ensure_org_row_for_internal_routes(session: Session, organisation_id: str) -> None:
    """
    credit_wallets and media_assets FK to organisations.id.
    If the DB was partially seeded or drifted, inserts can 500 with IntegrityError.
    In non-production, auto-create the canonical dev org row only for org_dev_demo.
    """
    if session.get(Organisation, organisation_id) is not None:
        return
    env = (get_settings().app_env or "").strip().lower()
    if env not in ("production", "prod") and organisation_id == _DEV_ORG_ID:
        session.add(
            Organisation(
                id=_DEV_ORG_ID,
                name="FeedFoundry Dev Org",
                slug="demo-creator",
            )
        )
        session.flush()
        return

    raise OrganisationNotFound(organisation_id)
