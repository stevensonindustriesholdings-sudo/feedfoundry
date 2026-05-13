"""Billing Checkout routes (Stripe configuration) and webhook alias."""

from __future__ import annotations

from sqlmodel import Session

from app.models import CreditWallet, Organisation
from app.settings import get_settings


def test_billing_checkout_access_missing_stripe_secret_returns_503(api_client, db_session: Session, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    get_settings.cache_clear()
    db_session.add(Organisation(id="org_bill_1", name="B", slug="bill1"))
    db_session.add(CreditWallet(organisation_id="org_bill_1", balance_available=0))
    db_session.commit()
    try:
        r = api_client.post(
            "/v1/billing/checkout/access",
            headers={
                "Authorization": "Bearer test-internal-key",
                "X-Org-Id": "org_bill_1",
            },
        )
        assert r.status_code == 503
        body = r.json()["detail"]
        assert isinstance(body, dict)
        assert body.get("error") == "STRIPE_NOT_CONFIGURED"
    finally:
        get_settings.cache_clear()


def test_billing_checkout_access_missing_price_id_returns_503(api_client, db_session: Session, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_ANNUAL_ACCESS_PRICE_ID", "")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:3000")
    get_settings.cache_clear()
    db_session.add(Organisation(id="org_bill_2", name="B2", slug="bill2"))
    db_session.add(CreditWallet(organisation_id="org_bill_2", balance_available=0))
    db_session.commit()
    try:
        r = api_client.post(
            "/v1/billing/checkout/access",
            headers={
                "Authorization": "Bearer test-internal-key",
                "X-Org-Id": "org_bill_2",
            },
        )
        assert r.status_code == 503
        assert r.json()["detail"]["error"] == "STRIPE_PRICE_NOT_CONFIGURED"
    finally:
        get_settings.cache_clear()


def test_billing_webhook_alias_matches_stripe_route(api_client, sqlite_engine, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_value_32chars_min")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_ANNUAL_CORE_PRICE_ID", "price_annual_core")
    monkeypatch.setenv("STRIPE_CREDIT_PACK_100_PRICE_ID", "price_credits_100")
    monkeypatch.setenv("STRIPE_CREDIT_PACK_100_CREDITS", "100")
    monkeypatch.setenv("STRIPE_ANNUAL_CORE_INCLUDED_CREDITS", "300")
    get_settings.cache_clear()
    from sqlmodel import Session as DbSession

    from app.db import get_session
    from app.main import app

    org = Organisation(id="org_bill_route", name="R", slug="br")
    with DbSession(sqlite_engine) as s:
        s.add(org)
        s.add(CreditWallet(organisation_id=org.id, balance_available=0))
        s.commit()

    ev = {
        "id": "evt_billing_alias_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_billing_alias",
                "metadata": {"ff_organisation_id": "org_bill_route"},
                "client_reference_id": None,
                "customer": "cus_test_1",
                "payment_intent": "pi_test_alias",
                "line_items": {
                    "data": [
                        {
                            "price": {"id": "price_annual_core"},
                        }
                    ]
                },
            }
        },
    }

    from app.routes import stripe_webhooks as sw_mod

    monkeypatch.setattr(sw_mod.stripe_billing, "verify_stripe_event", lambda *a, **k: ev)

    def override_session():
        with DbSession(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        r = api_client.post(
            "/v1/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "t=0,v1=fake"},
        )
        assert r.status_code == 200
        assert r.json().get("outcome") == "processed"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
