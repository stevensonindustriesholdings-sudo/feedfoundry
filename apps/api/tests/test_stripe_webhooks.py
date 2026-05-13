from __future__ import annotations

from typing import Any

import pytest
import stripe
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    AnnualAccess,
    AnnualAccessStatus,
    CreditWallet,
    Organisation,
)
from app.services.billing import stripe_webhook as billing
from app.settings import get_settings


def _checkout_event(
    *,
    event_id: str,
    org_id: str,
    price_id: str,
    payment_intent: str = "pi_test_123",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "metadata": {"ff_organisation_id": org_id},
                "client_reference_id": None,
                "customer": "cus_test_1",
                "payment_intent": payment_intent,
                "line_items": {
                    "data": [
                        {
                            "price": {"id": price_id},
                        }
                    ]
                },
            }
        },
    }


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_value_32chars_min")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_ANNUAL_CORE_PRICE_ID", "price_annual_core")
    monkeypatch.setenv("STRIPE_CREDIT_PACK_100_PRICE_ID", "price_credits_100")
    monkeypatch.setenv("STRIPE_CREDIT_PACK_100_CREDITS", "100")
    monkeypatch.setenv("STRIPE_ANNUAL_CORE_INCLUDED_CREDITS", "300")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_valid_annual_access_event(db_session: Session, stripe_env):
    org = Organisation(id="org_stripe_1", name="O", slug="s1")
    db_session.add(org)
    db_session.add(CreditWallet(organisation_id=org.id, balance_available=0))
    db_session.commit()

    ev = _checkout_event(event_id="evt_annual_1", org_id=org.id, price_id="price_annual_core")
    settings = get_settings()
    billing.handle_checkout_session_completed(db_session, ev, settings=settings)
    db_session.commit()

    aa = db_session.exec(select(AnnualAccess).where(AnnualAccess.organisation_id == org.id)).first()
    assert aa is not None
    assert aa.status == AnnualAccessStatus.ACTIVE
    assert aa.plan_code == "creator_core"
    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
    assert wallet.balance_available == 300


def test_valid_credit_pack_event(db_session: Session, stripe_env):
    org = Organisation(id="org_stripe_2", name="O2", slug="s2")
    db_session.add(org)
    db_session.add(CreditWallet(organisation_id=org.id, balance_available=10))
    db_session.commit()

    ev = _checkout_event(event_id="evt_pack_1", org_id=org.id, price_id="price_credits_100")
    settings = get_settings()
    billing.handle_checkout_session_completed(db_session, ev, settings=settings)
    db_session.commit()

    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
    assert wallet.balance_available == 110


def test_duplicate_stripe_event_ignored(db_session: Session, stripe_env):
    org = Organisation(id="org_stripe_3", name="O3", slug="s3")
    db_session.add(org)
    db_session.add(CreditWallet(organisation_id=org.id, balance_available=0))
    db_session.commit()

    ev = _checkout_event(event_id="evt_dup_1", org_id=org.id, price_id="price_credits_100")
    settings = get_settings()
    r1 = billing.process_stripe_event(db_session, ev, settings=settings)
    assert r1.get("duplicate") is not True
    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
    bal_after_first = wallet.balance_available

    r2 = billing.process_stripe_event(db_session, ev, settings=settings)
    assert r2.get("duplicate") is True
    db_session.refresh(wallet)
    assert wallet.balance_available == bal_after_first


def test_invalid_signature_rejected(api_client: TestClient, stripe_env, monkeypatch):
    def boom(*_a, **_k):
        raise stripe.error.SignatureVerificationError("sig", "payload")

    from app.routes import stripe_webhooks as sw

    monkeypatch.setattr(sw.stripe_billing, "verify_stripe_event", boom)
    r = api_client.post(
        "/v1/stripe/webhook",
        data=b'{"id":"evt_x"}',
        headers={"Stripe-Signature": "t=1,v1=bad"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_signature"


def test_unknown_price_logged_no_crash(db_session: Session, stripe_env, caplog):
    import logging

    org = Organisation(id="org_stripe_4", name="O4", slug="s4")
    db_session.add(org)
    db_session.add(CreditWallet(organisation_id=org.id, balance_available=5))
    db_session.commit()

    ev = _checkout_event(event_id="evt_unknown", org_id=org.id, price_id="price_totally_unknown")
    settings = get_settings()
    with caplog.at_level(logging.INFO):
        out = billing.handle_checkout_session_completed(db_session, ev, settings=settings)
    assert out == "noop_unknown_price"
    wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
    assert wallet.balance_available == 5


def test_full_route_valid_checkout(api_client: TestClient, sqlite_engine, stripe_env, monkeypatch):
    from app.db import get_session
    from app.main import app

    org = Organisation(id="org_route_1", name="R", slug="sr")
    with Session(sqlite_engine) as s:
        s.add(org)
        s.add(CreditWallet(organisation_id=org.id, balance_available=0))
        s.commit()

    ev = _checkout_event(event_id="evt_route_1", org_id="org_route_1", price_id="price_annual_core")

    from app.routes import stripe_webhooks as sw_mod

    monkeypatch.setattr(sw_mod.stripe_billing, "verify_stripe_event", lambda *a, **k: ev)

    def override_session():
        with Session(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        r = api_client.post(
            "/v1/stripe/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "t=0,v1=fake"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("received") is True
        assert body.get("outcome") == "processed"
    finally:
        app.dependency_overrides.clear()


def test_mvp_annual_access_price_grants_wallet_and_access(db_session: Session, monkeypatch):
    monkeypatch.setenv("STRIPE_ANNUAL_ACCESS_PRICE_ID", "price_mvp_annual_only")
    monkeypatch.setenv("STRIPE_ANNUAL_ACCESS_INCLUDED_MINUTES", "300")
    get_settings.cache_clear()
    org = Organisation(id="org_mvp_stripe", name="M", slug="mvpst")
    db_session.add(org)
    db_session.add(CreditWallet(organisation_id=org.id, balance_available=0))
    db_session.commit()
    try:
        ev = _checkout_event(event_id="evt_mvp_1", org_id=org.id, price_id="price_mvp_annual_only")
        settings = get_settings()
        billing.handle_checkout_session_completed(db_session, ev, settings=settings)
        db_session.commit()
        aa = db_session.exec(select(AnnualAccess).where(AnnualAccess.organisation_id == org.id)).first()
        assert aa is not None
        assert aa.plan_code == "annual_access"
        wallet = db_session.exec(select(CreditWallet).where(CreditWallet.organisation_id == org.id)).one()
        assert wallet.balance_available == 300
    finally:
        get_settings.cache_clear()
