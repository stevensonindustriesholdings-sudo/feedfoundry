import pytest

from app.config.env_validation import (
    collect_readiness,
    validate_settings_for_startup,
    validate_startup_bootstrap,
)
from app.settings import Settings


def test_bootstrap_staging_allows_missing_r2_stripe_public_url():
    """Staging can boot for /health; full checks remain on /ready and validate_settings_for_startup."""
    s = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://u:p@localhost:5432/ff",
        ff_internal_api_key="x" * 32,
        public_api_base_url="",
        stripe_secret_key="",
        stripe_webhook_secret="",
        r2_account_id="",
    )
    validate_startup_bootstrap(s)
    with pytest.raises(ValueError) as ei:
        validate_settings_for_startup(s)
    err = str(ei.value)
    assert "R2" in err or "STRIPE" in err or "PUBLIC" in err


def test_bootstrap_production_requires_r2():
    s = Settings(
        app_env="production",
        database_url="postgresql+psycopg://u:p@localhost:5432/ff",
        ff_internal_api_key="x" * 32,
        public_api_base_url="https://api.example.com",
        stripe_secret_key="sk_test_1234567890",
        stripe_webhook_secret="whsec_12345678901234567890123456789012",
        r2_account_id="",
        r2_access_key_id="",
        r2_secret_access_key="",
    )
    with pytest.raises(ValueError) as ei:
        validate_startup_bootstrap(s)
    assert "R2" in str(ei.value)


def test_validate_staging_fails_without_r2():
    s = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://u:p@localhost:5432/ff",
        ff_internal_api_key="x" * 32,
        public_api_base_url="https://api.example.com",
        stripe_secret_key="sk_test_1234567890",
        stripe_webhook_secret="whsec_12345678901234567890123456789012",
        r2_account_id="",
        r2_access_key_id="",
        r2_secret_access_key="",
    )
    with pytest.raises(ValueError) as ei:
        validate_settings_for_startup(s)
    assert "R2" in str(ei.value)


def test_validate_production_requires_https_public_url():
    s = Settings(
        app_env="production",
        database_url="postgresql+psycopg://u:p@localhost:5432/ff",
        ff_internal_api_key="x" * 32,
        public_api_base_url="http://insecure.example.com",
        stripe_secret_key="sk_test_1234567890",
        stripe_webhook_secret="whsec_12345678901234567890123456789012",
        r2_account_id="acc",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket_source="b1",
        r2_bucket_outputs="b2",
    )
    with pytest.raises(ValueError) as ei:
        validate_settings_for_startup(s)
    assert "https" in str(ei.value).lower()


def test_collect_readiness_has_subsystems(sqlite_engine):
    """Uses live app settings + sqlite from conftest (DATABASE_URL set)."""
    from app.settings import get_settings

    body = collect_readiness(get_settings())
    assert "checks" in body
    assert body["checks"]["database"]["ready"] is True
