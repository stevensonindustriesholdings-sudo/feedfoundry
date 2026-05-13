"""Reserve organisation processing minutes for jobs (goodwill shortfall rules)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Union

from sqlalchemy import extract
from sqlmodel import Session, func, select

from app.models import CreditTransaction, CreditTransactionType
from app.services.credit_ledger import (
    CreditLedgerError,
    grant_goodwill_processing_minutes,
    ledger_reserve_key,
    reserve_credits,
)
from app.settings import Settings


@dataclass
class ProcessingReservationSuccess:
    allowed: bool = True
    goodwill_minutes: int = 0
    available_minutes_before: int = 0
    estimated_minutes: int = 0


@dataclass
class ProcessingReservationBlocked:
    allowed: bool = False
    error: str = "INSUFFICIENT_PROCESSING_TIME"
    message: str = ""
    available_minutes: int = 0
    estimated_minutes: int = 0
    shortfall_minutes: int = 0


ProcessingReservationResult = Union[ProcessingReservationSuccess, ProcessingReservationBlocked]


def goodwill_idempotency_key(job_id: str) -> str:
    return f"ff:job:{job_id}:goodwill_grant"


def sum_goodwill_minutes_calendar_year(session: Session, organisation_id: str, *, year: int) -> int:
    """Total goodwill minutes granted in a calendar year (UTC)."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        year_clause = extract("year", CreditTransaction.created_at) == year
    else:
        year_clause = func.strftime("%Y", CreditTransaction.created_at) == str(year)
    stmt = select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
        CreditTransaction.organisation_id == organisation_id,
        CreditTransaction.type == CreditTransactionType.GOODWILL_GRANT,
        year_clause,
    )
    row = session.exec(stmt).one()
    if row is None:
        return 0
    if isinstance(row, (int, float)):
        return int(row)
    return int(row[0])


def reserve_processing_time_for_job(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    estimated_minutes: int,
    settings: Settings,
) -> ProcessingReservationResult:
    """Apply goodwill rules, then reserve ``estimated_minutes`` on the wallet (1 unit = 1 minute)."""
    if estimated_minutes < 1:
        estimated_minutes = 1

    from app.services.credit_ledger import get_wallet_for_update  # local import avoids cycles

    wallet = get_wallet_for_update(session, organisation_id)
    available = int(wallet.balance_available)
    est = int(estimated_minutes)

    if available >= est:
        try:
            reserve_credits(
                session,
                organisation_id=organisation_id,
                job_id=job_id,
                amount=est,
                idempotency_key=ledger_reserve_key(job_id),
            )
        except CreditLedgerError:
            return ProcessingReservationBlocked(
                message="Could not reserve processing time.",
                available_minutes=available,
                estimated_minutes=est,
                shortfall_minutes=max(0, est - available),
            )
        return ProcessingReservationSuccess(
            goodwill_minutes=0,
            available_minutes_before=available,
            estimated_minutes=est,
        )

    shortfall = est - available
    max_shortfall = int(settings.ff_goodwill_max_shortfall_minutes)
    annual_cap = int(settings.ff_goodwill_max_minutes_per_account_per_year)

    if shortfall <= max_shortfall:
        now_y = datetime.now(timezone.utc).year
        used_ytd = sum_goodwill_minutes_calendar_year(session, organisation_id, year=now_y)
        # TODO: when billing hardens, tie goodwill cap to subscription anniversary instead of calendar year.
        if used_ytd + shortfall > annual_cap:
            return ProcessingReservationBlocked(
                message=(
                    f"This upload needs {est} processing minutes but only {available} remain "
                    f"({shortfall} short). Annual goodwill allowance is exhausted."
                ),
                available_minutes=available,
                estimated_minutes=est,
                shortfall_minutes=shortfall,
            )
        try:
            grant_goodwill_processing_minutes(
                session,
                organisation_id=organisation_id,
                job_id=job_id,
                minutes=shortfall,
                idempotency_key=goodwill_idempotency_key(job_id),
            )
            reserve_credits(
                session,
                organisation_id=organisation_id,
                job_id=job_id,
                amount=est,
                idempotency_key=ledger_reserve_key(job_id),
            )
        except CreditLedgerError:
            return ProcessingReservationBlocked(
                message="Could not reserve processing time after goodwill grant.",
                available_minutes=available,
                estimated_minutes=est,
                shortfall_minutes=shortfall,
            )
        return ProcessingReservationSuccess(
            goodwill_minutes=shortfall,
            available_minutes_before=available,
            estimated_minutes=est,
        )

    return ProcessingReservationBlocked(
        message=(
            f"This upload needs {est} processing minutes but only {available} remain "
            f"({shortfall} short)."
        ),
        available_minutes=available,
        estimated_minutes=est,
        shortfall_minutes=shortfall,
    )
