"""Stripe Checkout entrypoints for MVP annual access and processing-time top-ups."""

from __future__ import annotations

import logging
from typing import Any, Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.routes.stripe_webhooks import stripe_webhook as stripe_webhook_handler
from app.settings import get_settings

log = logging.getLogger("feedfoundry.billing.routes")

router = APIRouter(prefix="/billing", tags=["billing"])


def _stripe_secret_or_503(settings: Any) -> str:
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "STRIPE_NOT_CONFIGURED",
                "message": "Stripe is not configured (missing STRIPE_SECRET_KEY).",
            },
        )
    return key


def _checkout_return_base(settings: Any) -> str:
    base = (settings.app_base_url or settings.public_api_base_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "APP_BASE_URL_MISSING",
                "message": "Set APP_BASE_URL or PUBLIC_API_BASE_URL for Checkout return URLs.",
            },
        )
    return base


@router.post("/checkout/access")
def post_checkout_annual_access(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Create a Stripe Checkout Session for annual archive access (+ included processing minutes)."""
    _ = session
    settings = get_settings()
    key = _stripe_secret_or_503(settings)
    price = (settings.stripe_annual_access_price_id or "").strip()
    if not price:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "STRIPE_PRICE_NOT_CONFIGURED",
                "message": "STRIPE_ANNUAL_ACCESS_PRICE_ID is not set.",
            },
        )
    stripe.api_key = key
    base = _checkout_return_base(settings)
    try:
        sess = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price, "quantity": 1}],
            success_url=f"{base}/dashboard?checkout=access_success=1",
            cancel_url=f"{base}/dashboard?checkout=cancelled=1",
            client_reference_id=organisation_id,
            metadata={
                "ff_organisation_id": organisation_id,
                "product_type": "annual_access",
                "access_months": "12",
                "included_processing_minutes": str(int(settings.stripe_annual_access_included_minutes)),
            },
        )
    except stripe.error.StripeError as exc:
        log.exception("stripe_checkout_access_failed")
        msg = getattr(exc, "user_message", None) or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "stripe_error", "message": msg},
        ) from exc
    return {"checkout_url": str(sess.url), "session_id": str(sess.id)}


@router.post("/checkout/processing-time")
def post_checkout_processing_time(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Create a Stripe Checkout Session for a processing-time top-up (minutes on the wallet)."""
    _ = session
    settings = get_settings()
    key = _stripe_secret_or_503(settings)
    price = (settings.stripe_processing_time_price_id or "").strip()
    if not price:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "STRIPE_PRICE_NOT_CONFIGURED",
                "message": "STRIPE_PROCESSING_TIME_PRICE_ID is not set.",
            },
        )
    stripe.api_key = key
    base = _checkout_return_base(settings)
    try:
        sess = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price, "quantity": 1}],
            success_url=f"{base}/dashboard?checkout=topup_success=1",
            cancel_url=f"{base}/dashboard?checkout=cancelled=1",
            client_reference_id=organisation_id,
            metadata={
                "ff_organisation_id": organisation_id,
                "product_type": "processing_time_topup",
                "processing_minutes": str(int(settings.stripe_processing_time_pack_minutes)),
            },
        )
    except stripe.error.StripeError as exc:
        log.exception("stripe_checkout_topup_failed")
        msg = getattr(exc, "user_message", None) or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "stripe_error", "message": msg},
        ) from exc
    return {"checkout_url": str(sess.url), "session_id": str(sess.id)}


@router.post("/webhook")
async def billing_stripe_webhook(
    request: Request,
    session: Session = Depends(get_session),
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
):
    """Same handler as ``POST /v1/stripe/webhook`` — Stripe Dashboard can target either URL."""
    return await stripe_webhook_handler(request, session, stripe_signature)
