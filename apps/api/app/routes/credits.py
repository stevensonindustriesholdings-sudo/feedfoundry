"""Account balance: annual hosted archive + processing allowance (ledger).

**Flow:** ``POST /v1/jobs`` reserves estimated **processing minutes** on the wallet;
the worker completes debits from the reservation, or releases it on failure/cancel
(see ``credit_ledger`` reserve / debit / release helpers — internal names unchanged).
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.schemas.api import AccountProcessingBalanceResponse
from app.schemas.processing_display import processing_minutes_to_approx_hours
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import get_or_create_wallet

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


def _account_processing_balance(
    *,
    organisation_id: str,
    session: Session,
) -> AccountProcessingBalanceResponse:
    wallet = get_or_create_wallet(session, organisation_id)
    session.refresh(wallet)
    aa = annual_access_svc.get_latest_annual_access(session, organisation_id)
    if not aa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "annual_archive_access_not_configured",
                "message": "No annual hosted archive record exists for this organisation.",
            },
        )
    period_end = _calendar_day_iso(aa.period_end)
    avail = int(wallet.balance_available)
    body = AccountProcessingBalanceResponse(
        annual_archive_access_status=_enum_str(aa.status),
        hosting_until=_calendar_day_iso(aa.hosting_until),
        processing_minutes_available=avail,
        processing_minutes_reserved=int(wallet.balance_reserved),
        processing_minutes_used_lifetime=int(wallet.balance_spent_lifetime),
        processing_period_ends_on=period_end,
        processing_hours_available=processing_minutes_to_approx_hours(avail) or 0.0,
    )
    session.commit()
    return body


@router.get(
    "",
    response_model=AccountProcessingBalanceResponse,
    summary="Account: archive access and processing allowance",
)
def get_account(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> AccountProcessingBalanceResponse:
    return _account_processing_balance(organisation_id=organisation_id, session=session)


@router.get(
    "/usage",
    response_model=AccountProcessingBalanceResponse,
    summary="Same as GET /v1/account (processing minutes + annual access)",
)
def get_account_usage(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> AccountProcessingBalanceResponse:
    return _account_processing_balance(organisation_id=organisation_id, session=session)


@router.get(
    "/credits",
    response_model=AccountProcessingBalanceResponse,
    deprecated=True,
    summary="Deprecated path — use GET /v1/account or /v1/account/usage",
)
def get_account_credits_legacy(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> AccountProcessingBalanceResponse:
    return _account_processing_balance(organisation_id=organisation_id, session=session)
