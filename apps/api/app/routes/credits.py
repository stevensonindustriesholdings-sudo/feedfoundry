from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.schemas.api import AccountCreditsResponse
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import get_or_create_wallet
from app.services.processing_time import sum_goodwill_minutes_calendar_year

router = APIRouter(prefix="/account", tags=["account"])


def _enum_str(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _calendar_day_iso(value: object | None) -> str | None:
    """DB drivers may return `date` or `datetime`; avoid calling `.date()` on a bare `date`."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


@router.get("/credits", response_model=AccountCreditsResponse)
def get_credits(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> AccountCreditsResponse:
    wallet = get_or_create_wallet(session, organisation_id)
    # Inner wallet helper used to commit mid-request; refresh so fields are not expired on read.
    session.refresh(wallet)
    aa = annual_access_svc.get_latest_annual_access(session, organisation_id)
    if not aa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="annual_access_not_configured",
        )
    period_end = _calendar_day_iso(aa.period_end)
    now_y = datetime.now(timezone.utc).year
    goodwill_ytd = sum_goodwill_minutes_calendar_year(session, organisation_id, year=now_y)
    body = AccountCreditsResponse(
        annual_access_status=_enum_str(aa.status),
        hosting_until=_calendar_day_iso(aa.hosting_until),
        processing_minutes_available=wallet.balance_available,
        processing_minutes_reserved=wallet.balance_reserved,
        processing_minutes_used_lifetime=wallet.balance_spent_lifetime,
        goodwill_processing_minutes_granted_ytd=goodwill_ytd,
        next_processing_period_end=period_end,
        credits_available=wallet.balance_available,
        credits_reserved=wallet.balance_reserved,
        credits_spent_lifetime=wallet.balance_spent_lifetime,
        next_credit_expiry=period_end,
    )
    session.commit()
    return body
