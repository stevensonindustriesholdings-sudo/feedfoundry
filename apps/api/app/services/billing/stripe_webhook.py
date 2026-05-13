"""
Stripe webhook processing: signature verification, idempotency, price mapping, ledger updates.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Literal, Optional, Union

import stripe
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    AnnualAccessStatus,
    CreditTransaction,
    CreditTransactionType,
    Organisation,
    StripeWebhookEvent,
    utcnow,
)
from app.services.credit_ledger import (
    claw_back_credits_for_stripe_refund,
    grant_annual_credits_from_stripe,
    purchase_credits_from_stripe,
)
from app.settings import Settings, get_settings

log = logging.getLogger("feedfoundry.billing.stripe")

Outcome = Literal[
    "processed",
    "noop_duplicate",
    "noop_unknown_price",
    "noop_missing_org",
    "noop_unhandled_event",
    "noop_no_line_items",
    "processed_refund_credits",
    "processed_refund_annual",
    "noop_refund_no_match",
]


def verify_stripe_event(
    payload: bytes,
    sig_header: Optional[str],
    *,
    settings: Optional[Settings] = None,
) -> Union[stripe.Event, dict[str, Any]]:
    """
    Verify Stripe-Signature. Raises stripe.error.SignatureVerificationError on bad signature.
    """
    s = settings or get_settings()
    secret = (s.stripe_webhook_secret or "").strip()
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
    if not sig_header:
        raise stripe.error.SignatureVerificationError(
            sig_header or "",
            payload,
            message="Missing Stripe-Signature header",
        )
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def _event_id(event: Any) -> str:
    if isinstance(event, dict):
        return str(event["id"])
    return str(event.id)


def _event_type(event: Any) -> str:
    if isinstance(event, dict):
        return str(event["type"])
    return str(event.type)


def _data_object(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        raw = event.get("data", {}).get("object")
    else:
        raw = event.data.object
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "to_dict_recursive"):
        return raw.to_dict_recursive()  # type: ignore[no-any-return]
    if hasattr(raw, "to_dict"):
        return raw.to_dict()  # type: ignore[no-any-return]
    return dict(raw)  # type: ignore[arg-type]


def _checkout_session_line_items(
    session_obj: dict[str, Any],
    *,
    settings: Settings,
) -> list[dict[str, Any]]:
    li = session_obj.get("line_items")
    if isinstance(li, dict) and isinstance(li.get("data"), list):
        return [x for x in li["data"] if isinstance(x, dict)]
    api_key = (settings.stripe_secret_key or "").strip()
    session_id = session_obj.get("id")
    if not api_key or not session_id:
        return []
    stripe.api_key = api_key
    full = stripe.checkout.Session.retrieve(
        session_id,
        expand=["line_items.data.price"],
    )
    fd = full.to_dict() if hasattr(full, "to_dict") else dict(full)
    li2 = fd.get("line_items") or {}
    data = li2.get("data") or []
    return [x for x in data if isinstance(x, dict)]


def _line_item_price_ids(line_items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in line_items:
        price = row.get("price")
        if isinstance(price, dict) and price.get("id"):
            out.append(str(price["id"]))
        elif isinstance(price, str):
            out.append(price)
    return out


def _resolve_organisation_id(session_obj: dict[str, Any]) -> Optional[str]:
    md = session_obj.get("metadata") or {}
    if not isinstance(md, dict):
        md = {}
    return (
        md.get("ff_organisation_id")
        or md.get("organisation_id")
        or session_obj.get("client_reference_id")
    )


def _annual_plan_for_price(
    price_id: str, settings: Settings
) -> Optional[tuple[str, int]]:
    """Returns (plan_code, included_credits) or None."""
    pid = (price_id or "").strip()
    if not pid:
        return None
    if pid == (settings.stripe_annual_core_price_id or "").strip():
        return (settings.stripe_annual_core_plan_code, settings.stripe_annual_core_included_credits)
    if pid == (settings.stripe_annual_lite_price_id or "").strip():
        return (settings.stripe_annual_lite_plan_code, settings.stripe_annual_lite_included_credits)
    if pid == (settings.stripe_annual_studio_price_id or "").strip():
        return (settings.stripe_annual_studio_plan_code, settings.stripe_annual_studio_included_credits)
    return None


def _credit_pack_credits(price_id: str, settings: Settings) -> Optional[int]:
    pid = (price_id or "").strip()
    if not pid:
        return None
    if pid == (settings.stripe_credit_pack_100_price_id or "").strip():
        return settings.stripe_credit_pack_100_credits
    if pid == (settings.stripe_credit_pack_500_price_id or "").strip():
        return settings.stripe_credit_pack_500_credits
    if pid == (settings.stripe_credit_pack_1500_price_id or "").strip():
        return settings.stripe_credit_pack_1500_credits
    return None


def _mvp_checkout_plan(price_id: str, settings: Settings) -> Optional[tuple[str, str, int]]:
    """MVP single-price annual access or processing-time top-up (minutes on wallet).

    Returns ``(kind, plan_code, minutes)`` where ``kind`` is ``annual`` or ``topup``.
    ``plan_code`` is only used for annual rows (``annual_access`` for the unified SKU).
    """
    pid = (price_id or "").strip()
    ap = (settings.stripe_annual_access_price_id or "").strip()
    if ap and pid == ap:
        return ("annual", "annual_access", int(settings.stripe_annual_access_included_minutes))
    tp = (settings.stripe_processing_time_price_id or "").strip()
    if tp and pid == tp:
        return ("topup", "", int(settings.stripe_processing_time_pack_minutes))
    return None


def _sync_org_customer(session: Session, org_id: str, customer_id: Optional[str]) -> None:
    if not customer_id:
        return
    org = session.get(Organisation, org_id)
    if org and not org.stripe_customer_id:
        org.stripe_customer_id = customer_id
        org.updated_at = utcnow()
        session.add(org)


def _extend_or_create_annual_access(
    session: Session,
    *,
    organisation_id: str,
    plan_code: str,
    included_credits: int,
    checkout_session_id: str,
    payment_intent_id: Optional[str],
    stripe_event_id: str,
    settings: Settings,
) -> None:
    now = utcnow()
    days = int(settings.stripe_annual_access_period_days)
    stmt = (
        select(AnnualAccess)
        .where(AnnualAccess.organisation_id == organisation_id)
        .order_by(desc(AnnualAccess.period_end))
    )
    aa = session.exec(stmt).first()

    if aa and aa.status in (AnnualAccessStatus.ACTIVE, AnnualAccessStatus.GRACE):
        anchor = max(now, aa.period_end)
        new_end = anchor + timedelta(days=days)
        aa.period_end = new_end
        aa.hosting_until = new_end
        aa.plan_code = plan_code
        aa.included_credits = included_credits
        aa.stripe_checkout_session_id = checkout_session_id
        if payment_intent_id:
            aa.stripe_payment_intent_id = payment_intent_id
        aa.status = AnnualAccessStatus.ACTIVE
        aa.updated_at = now
        session.add(aa)
    else:
        session.add(
            AnnualAccess(
                organisation_id=organisation_id,
                plan_code=plan_code,
                status=AnnualAccessStatus.ACTIVE,
                period_start=now,
                period_end=now + timedelta(days=days),
                hosting_until=now + timedelta(days=days),
                included_credits=included_credits,
                stripe_checkout_session_id=checkout_session_id,
                stripe_payment_intent_id=payment_intent_id,
            )
        )

    if included_credits > 0:
        grant_annual_credits_from_stripe(
            session,
            organisation_id=organisation_id,
            credits=included_credits,
            idempotency_key=f"stripe:event:{stripe_event_id}:annual_grant",
            stripe_reference=payment_intent_id or checkout_session_id,
            memo=f"annual_access_included_credits:{plan_code}",
        )


def handle_checkout_session_completed(
    session: Session,
    event: Any,
    *,
    settings: Settings,
) -> Outcome:
    obj = _data_object(event)
    event_id = _event_id(event)
    line_items = _checkout_session_line_items(obj, settings=settings)
    if not line_items:
        log.warning("checkout.session.completed without line_items session=%s", obj.get("id"))
        return "noop_no_line_items"

    org_id = _resolve_organisation_id(obj)
    price_ids = _line_item_price_ids(line_items)
    if not price_ids:
        return "noop_no_line_items"

    customer_id = obj.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    checkout_session_id = str(obj.get("id") or "")
    payment_intent = obj.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    payment_intent_id = str(payment_intent) if payment_intent else None

    outcome: Outcome = "noop_unhandled_event"
    matched_known_price = False

    for price_id in price_ids:
        mvp = _mvp_checkout_plan(price_id, settings)
        annual = _annual_plan_for_price(price_id, settings)
        credits_pack = _credit_pack_credits(price_id, settings)

        if mvp is None and annual is None and credits_pack is None:
            log.info("stripe_unknown_price_id price_id=%s event_id=%s", price_id, event_id)
            continue

        matched_known_price = True

        if not org_id:
            log.warning("stripe_checkout_missing_org metadata session=%s", checkout_session_id)
            return "noop_missing_org"

        org = session.get(Organisation, org_id)
        if not org:
            log.warning("stripe_checkout_unknown_org org_id=%s", org_id)
            return "noop_missing_org"

        _sync_org_customer(session, org_id, str(customer_id) if customer_id else None)

        if mvp:
            kind, plan_code, minutes = mvp
            if kind == "annual":
                _extend_or_create_annual_access(
                    session,
                    organisation_id=org_id,
                    plan_code=plan_code,
                    included_credits=minutes,
                    checkout_session_id=checkout_session_id,
                    payment_intent_id=payment_intent_id,
                    stripe_event_id=event_id,
                    settings=settings,
                )
            else:
                purchase_credits_from_stripe(
                    session,
                    organisation_id=org_id,
                    credits=minutes,
                    idempotency_key=f"stripe:event:{event_id}:processing_topup:{price_id}",
                    stripe_reference=payment_intent_id or checkout_session_id,
                    memo="processing_time_topup",
                )
            outcome = "processed"
        elif annual:
            plan_code, included = annual
            _extend_or_create_annual_access(
                session,
                organisation_id=org_id,
                plan_code=plan_code,
                included_credits=included,
                checkout_session_id=checkout_session_id,
                payment_intent_id=payment_intent_id,
                stripe_event_id=event_id,
                settings=settings,
            )
            outcome = "processed"
        elif credits_pack is not None:
            purchase_credits_from_stripe(
                session,
                organisation_id=org_id,
                credits=credits_pack,
                idempotency_key=f"stripe:event:{event_id}:credit_pack:{price_id}",
                stripe_reference=payment_intent_id or checkout_session_id,
                memo=f"stripe_credit_pack:{price_id}",
            )
            outcome = "processed"

    if not matched_known_price:
        return "noop_unknown_price"
    return outcome


def handle_charge_refunded(
    session: Session,
    event: Any,
    *,
    settings: Settings,
) -> Outcome:
    _ = settings
    charge = _data_object(event)
    event_id = _event_id(event)
    pi = charge.get("payment_intent")
    if isinstance(pi, dict):
        pi = pi.get("id")
    if not pi:
        return "noop_refund_no_match"
    pi_str = str(pi)

    stmt = (
        select(CreditTransaction)
        .where(
            CreditTransaction.stripe_reference == pi_str,
            CreditTransaction.type == CreditTransactionType.PURCHASE,
        )
        .order_by(desc(CreditTransaction.created_at))
    )
    purchase = session.exec(stmt).first()
    if purchase:
        refunded = session.exec(
            select(CreditTransaction).where(
                CreditTransaction.stripe_reference == pi_str,
                CreditTransaction.type == CreditTransactionType.REFUND,
            )
        ).all()
        already = sum(int(t.amount) for t in refunded)
        remaining = int(purchase.amount) - already
        if remaining <= 0:
            return "noop_refund_no_match"
        claw_back_credits_for_stripe_refund(
            session,
            organisation_id=purchase.organisation_id,
            credits=remaining,
            idempotency_key=f"stripe:event:{event_id}:refund_clawback",
            stripe_reference=pi_str,
            memo="stripe_charge_refunded",
        )
        return "processed_refund_credits"

    grant = session.exec(
        select(CreditTransaction)
        .where(
            CreditTransaction.stripe_reference == pi_str,
            CreditTransaction.type == CreditTransactionType.ANNUAL_GRANT,
        )
        .order_by(desc(CreditTransaction.created_at))
    ).first()
    if grant:
        refunded = session.exec(
            select(CreditTransaction).where(
                CreditTransaction.stripe_reference == pi_str,
                CreditTransaction.type == CreditTransactionType.REFUND,
            )
        ).all()
        already = sum(int(t.amount) for t in refunded)
        remaining = int(grant.amount) - already
        if remaining > 0:
            claw_back_credits_for_stripe_refund(
                session,
                organisation_id=grant.organisation_id,
                credits=remaining,
                idempotency_key=f"stripe:event:{event_id}:refund_annual_grant_clawback",
                stripe_reference=pi_str,
                memo="stripe_charge_refunded_annual_grant",
            )
        stmt_aa = select(AnnualAccess).where(AnnualAccess.stripe_payment_intent_id == pi_str)
        for aa in session.exec(stmt_aa).all():
            if aa.status != AnnualAccessStatus.CANCELLED:
                aa.status = AnnualAccessStatus.CANCELLED
                aa.updated_at = utcnow()
                session.add(aa)
        return "processed_refund_annual"

    stmt_aa = select(AnnualAccess).where(AnnualAccess.stripe_payment_intent_id == pi_str)
    rows = list(session.exec(stmt_aa).all())
    if rows:
        for aa in rows:
            aa.status = AnnualAccessStatus.CANCELLED
            aa.updated_at = utcnow()
            session.add(aa)
        return "processed_refund_annual"

    log.info("stripe_refund_no_ledger_match payment_intent=%s event_id=%s", pi_str, event_id)
    return "noop_refund_no_match"


def process_stripe_event(session: Session, event: Any, *, settings: Optional[Settings] = None) -> dict[str, Any]:
    """
    Apply one verified Stripe event inside ``session`` transaction.
    Inserts idempotency row first; duplicate ``evt_*`` ids are ignored without side effects.
    """
    s = settings or get_settings()
    event_id = _event_id(event)
    etype = _event_type(event)

    try:
        session.add(
            StripeWebhookEvent(
                stripe_event_id=event_id,
                event_type=etype,
                outcome="processing",
            )
        )
        session.flush()
    except IntegrityError:
        session.rollback()
        log.debug("stripe_duplicate_event event_id=%s", event_id)
        return {"received": True, "duplicate": True, "event_id": event_id}

    outcome: Outcome = "noop_unhandled_event"
    try:
        if etype == "checkout.session.completed":
            outcome = handle_checkout_session_completed(session, event, settings=s)
        elif etype == "charge.refunded":
            outcome = handle_charge_refunded(session, event, settings=s)
        else:
            log.debug("stripe_unhandled_event_type type=%s id=%s", etype, event_id)

        row = session.get(StripeWebhookEvent, event_id)
        if row:
            row.outcome = outcome
            session.add(row)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {"received": True, "event_id": event_id, "outcome": outcome}
