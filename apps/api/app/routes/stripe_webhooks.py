from __future__ import annotations

import logging
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from app.db import get_session
from app.services.billing import stripe_webhook as stripe_billing
from app.settings import get_settings

router = APIRouter(prefix="/stripe", tags=["stripe"])
log = logging.getLogger("feedfoundry.stripe")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Session = Depends(get_session),
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
):
    """
    Stripe webhook endpoint. Verifies ``Stripe-Signature``; duplicate ``evt_*`` ids are ignored.
    """
    settings = get_settings()
    body = await request.body()
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing_signature",
        )
    try:
        event = stripe_billing.verify_stripe_event(body, stripe_signature, settings=settings)
    except ValueError as e:
        log.error("stripe_webhook_misconfigured: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_webhook_not_configured",
        ) from e
    except stripe.error.SignatureVerificationError:
        log.warning("stripe_invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_signature",
        )

    result = stripe_billing.process_stripe_event(session, event, settings=settings)
    log.info("stripe_webhook_ok result=%s", result)
    return result
