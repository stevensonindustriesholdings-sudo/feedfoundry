"""Ensure production dependency set allows importing the FastAPI app (catches missing Docker deps)."""


def test_postgres_drivers_for_railway_database_url():
    """Railway DATABASE_URL is often postgresql://… (psycopg2); .env.example uses postgresql+psycopg:// (psycopg3)."""
    import psycopg  # noqa: F401
    import psycopg2  # noqa: F401

    from app.main import app

    assert app.title == "FeedFoundry API"


def test_app_main_and_stripe_import_chain():
    import stripe  # noqa: F401 — must be installed for webhook routes

    from app.main import app

    assert app.title == "FeedFoundry API"
