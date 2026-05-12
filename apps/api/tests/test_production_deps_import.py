"""Ensure production dependency set allows importing the FastAPI app (catches missing Docker deps)."""


def test_app_main_and_stripe_import_chain():
    import stripe  # noqa: F401 — must be installed for webhook routes

    from app.main import app

    assert app.title == "FeedFoundry API"
