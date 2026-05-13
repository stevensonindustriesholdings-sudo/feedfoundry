from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    utcnow,
)
from app.services.organisation_guard import ensure_org_row_for_internal_routes


class CreditLedgerError(Exception):
    pass


@dataclass
class WalletSnapshot:
    organisation_id: str
    balance_available: int
    balance_reserved: int
    balance_spent_lifetime: int


def ledger_reserve_key(job_id: str) -> str:
    return f"ff:job:{job_id}:reserve"


def ledger_debit_key(job_id: str) -> str:
    return f"ff:job:{job_id}:debit"


def ledger_release_remainder_key(job_id: str) -> str:
    return f"ff:job:{job_id}:release_remainder"


def ledger_release_failure_key(job_id: str) -> str:
    return f"ff:job:{job_id}:release_failure"


def ledger_goodwill_revoke_key(job_id: str) -> str:
    return f"ff:job:{job_id}:goodwill_revoke_on_failure"


def get_or_create_wallet(session: Session, organisation_id: str) -> CreditWallet:
    ensure_org_row_for_internal_routes(session, organisation_id)
    stmt = select(CreditWallet).where(CreditWallet.organisation_id == organisation_id)
    wallet = session.exec(stmt).first()
    if wallet:
        return wallet
    wallet = CreditWallet(organisation_id=organisation_id)
    session.add(wallet)
    session.flush()
    session.refresh(wallet)
    return wallet


def get_wallet_for_update(session: Session, organisation_id: str) -> CreditWallet:
    ensure_org_row_for_internal_routes(session, organisation_id)
    stmt = (
        select(CreditWallet)
        .where(CreditWallet.organisation_id == organisation_id)
        .with_for_update()
    )
    wallet = session.exec(stmt).first()
    if not wallet:
        wallet = CreditWallet(organisation_id=organisation_id)
        session.add(wallet)
        session.flush()
    return wallet


def _find_idempotent_txn(session: Session, idempotency_key: str) -> Optional[CreditTransaction]:
    if not idempotency_key:
        return None
    stmt = select(CreditTransaction).where(CreditTransaction.idempotency_key == idempotency_key)
    return session.exec(stmt).first()


def _snapshot_from_wallet(wallet: CreditWallet) -> WalletSnapshot:
    return WalletSnapshot(
        organisation_id=wallet.organisation_id,
        balance_available=wallet.balance_available,
        balance_reserved=wallet.balance_reserved,
        balance_spent_lifetime=wallet.balance_spent_lifetime,
    )


def _record_txn(
    session: Session,
    *,
    organisation_id: str,
    wallet_id: str,
    job_id: Optional[str],
    type_: CreditTransactionType,
    amount: int,
    balance_available_after: int,
    memo: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    stripe_reference: Optional[str] = None,
) -> None:
    txn = CreditTransaction(
        organisation_id=organisation_id,
        wallet_id=wallet_id,
        job_id=job_id,
        type=type_,
        amount=amount,
        balance_after=balance_available_after,
        memo=memo,
        idempotency_key=idempotency_key,
        stripe_reference=stripe_reference,
        created_at=datetime.now(timezone.utc),
    )
    session.add(txn)


def reserve_credits(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    amount: int,
    idempotency_key: str,
) -> WalletSnapshot:
    if amount < 0:
        raise CreditLedgerError("reserve amount must be non-negative")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    if wallet.balance_available < amount:
        raise CreditLedgerError("insufficient_available_credits")

    wallet.balance_available -= amount
    wallet.balance_reserved += amount
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=job_id,
        type_=CreditTransactionType.RESERVE,
        amount=amount,
        balance_available_after=wallet.balance_available,
        memo="processing_minutes_reserved",
        idempotency_key=idempotency_key,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def release_reserved_credits(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    amount: int,
    idempotency_key: str,
) -> WalletSnapshot:
    if amount < 0:
        raise CreditLedgerError("release amount must be non-negative")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    if wallet.balance_reserved < amount:
        raise CreditLedgerError("cannot_release_more_than_reserved")

    wallet.balance_reserved -= amount
    wallet.balance_available += amount
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=job_id,
        type_=CreditTransactionType.RELEASE,
        amount=amount,
        balance_available_after=wallet.balance_available,
        memo="processing_minutes_released",
        idempotency_key=idempotency_key,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def debit_reserved_credits(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    amount: int,
    idempotency_key: str,
) -> WalletSnapshot:
    if amount < 0:
        raise CreditLedgerError("debit amount must be non-negative")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    if wallet.balance_reserved < amount:
        raise CreditLedgerError("cannot_debit_more_than_reserved")

    wallet.balance_reserved -= amount
    wallet.balance_spent_lifetime += amount
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=job_id,
        type_=CreditTransactionType.DEBIT,
        amount=amount,
        balance_available_after=wallet.balance_available,
        memo="processing_minutes_used",
        idempotency_key=idempotency_key,
        stripe_reference=None,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def revoke_goodwill_processing_minutes_on_job_failure(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    minutes: int,
    idempotency_key: str,
) -> WalletSnapshot:
    """Remove goodwill minutes that were granted only for this job when the job fails."""
    if minutes <= 0:
        raise CreditLedgerError("revoke goodwill minutes must be positive")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    claw = min(wallet.balance_available, minutes)
    wallet.balance_available -= claw
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=job_id,
        type_=CreditTransactionType.GOODWILL_REVOKE,
        amount=claw,
        balance_available_after=wallet.balance_available,
        memo="goodwill_processing_minutes_revoked_job_failed",
        idempotency_key=idempotency_key,
        stripe_reference=None,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def purchase_credits_from_stripe(
    session: Session,
    *,
    organisation_id: str,
    credits: int,
    idempotency_key: str,
    stripe_reference: Optional[str] = None,
    memo: Optional[str] = None,
) -> WalletSnapshot:
    if credits <= 0:
        raise CreditLedgerError("credits must be positive")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    wallet.balance_available += credits
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=None,
        type_=CreditTransactionType.PURCHASE,
        amount=credits,
        balance_available_after=wallet.balance_available,
        memo=memo or "processing_minutes_granted",
        idempotency_key=idempotency_key,
        stripe_reference=stripe_reference,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def grant_goodwill_processing_minutes(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
    minutes: int,
    idempotency_key: str,
) -> WalletSnapshot:
    if minutes <= 0:
        raise CreditLedgerError("goodwill minutes must be positive")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    wallet.balance_available += minutes
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=job_id,
        type_=CreditTransactionType.GOODWILL_GRANT,
        amount=minutes,
        balance_available_after=wallet.balance_available,
        memo="goodwill_processing_minutes_granted",
        idempotency_key=idempotency_key,
        stripe_reference=None,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def admin_grant_processing_minutes(
    session: Session,
    *,
    organisation_id: str,
    minutes: int,
    idempotency_key: str,
    memo: Optional[str] = None,
) -> WalletSnapshot:
    if minutes <= 0:
        raise CreditLedgerError("minutes must be positive")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    wallet.balance_available += minutes
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=None,
        type_=CreditTransactionType.ADMIN_ADJUSTMENT,
        amount=minutes,
        balance_available_after=wallet.balance_available,
        memo=memo or "processing_minutes_granted",
        idempotency_key=idempotency_key,
        stripe_reference=None,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def grant_annual_credits_from_stripe(
    session: Session,
    *,
    organisation_id: str,
    credits: int,
    idempotency_key: str,
    stripe_reference: Optional[str] = None,
    memo: Optional[str] = None,
) -> WalletSnapshot:
    if credits < 0:
        raise CreditLedgerError("credits must be non-negative")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    wallet.balance_available += credits
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=None,
        type_=CreditTransactionType.ANNUAL_GRANT,
        amount=credits,
        balance_available_after=wallet.balance_available,
        memo=memo or "processing_minutes_granted",
        idempotency_key=idempotency_key,
        stripe_reference=stripe_reference,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)


def claw_back_credits_for_stripe_refund(
    session: Session,
    *,
    organisation_id: str,
    credits: int,
    idempotency_key: str,
    stripe_reference: Optional[str] = None,
    memo: Optional[str] = None,
) -> WalletSnapshot:
    """Remove credits previously granted or purchased (compensating transaction)."""
    if credits <= 0:
        raise CreditLedgerError("credits must be positive")
    if not idempotency_key:
        raise CreditLedgerError("idempotency_key required")

    wallet = get_wallet_for_update(session, organisation_id)
    existing = _find_idempotent_txn(session, idempotency_key)
    if existing:
        session.refresh(wallet)
        return _snapshot_from_wallet(wallet)

    claw = min(wallet.balance_available, credits)
    wallet.balance_available -= claw
    wallet.updated_at = utcnow()
    session.add(wallet)
    _record_txn(
        session,
        organisation_id=organisation_id,
        wallet_id=wallet.id,
        job_id=None,
        type_=CreditTransactionType.REFUND,
        amount=claw,
        balance_available_after=wallet.balance_available,
        memo=memo or "stripe_refund_credit_clawback",
        idempotency_key=idempotency_key,
        stripe_reference=stripe_reference,
    )
    session.flush()
    return _snapshot_from_wallet(wallet)
