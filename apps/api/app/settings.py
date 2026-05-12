from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "feedfoundry"
    public_api_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+psycopg://user:password@localhost:5432/feedfoundry"

    ff_internal_api_key: str = "replace_me"
    base44_webhook_secret: str = "replace_me"

    ai_routing_config_path: Path = _REPO_ROOT / "ai-routing.yaml"

    api_version: str = "0.1.0"

    # Build metadata (set in CI / Railway)
    git_commit: str = ""
    build_timestamp: str = ""

    # Worker-related (API logs readiness; worker reads same env names)
    worker_poll_interval_seconds: int = 5
    storage_provider: str = "r2"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_source: str = "feedfoundry-source-dev"
    r2_bucket_outputs: str = "feedfoundry-outputs-dev"
    r2_public_base_url: str = ""
    storage_presign_put_expires_seconds: int = 900
    storage_presign_get_expires_seconds: int = 900

    # Stripe (webhooks + Checkout mapping)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_annual_core_price_id: str = ""
    stripe_annual_lite_price_id: str = ""
    stripe_annual_studio_price_id: str = ""
    stripe_credit_pack_100_price_id: str = ""
    stripe_credit_pack_500_price_id: str = ""
    stripe_credit_pack_1500_price_id: str = ""
    stripe_annual_core_plan_code: str = "creator_core"
    stripe_annual_lite_plan_code: str = "podcast_lite"
    stripe_annual_studio_plan_code: str = "creator_studio"
    stripe_annual_access_period_days: int = 365
    stripe_credit_pack_100_credits: int = 100
    stripe_credit_pack_500_credits: int = 500
    stripe_credit_pack_1500_credits: int = 1500
    stripe_annual_core_included_credits: int = 300
    stripe_annual_lite_included_credits: int = 100
    stripe_annual_studio_included_credits: int = 1500


@lru_cache
def get_settings() -> Settings:
    return Settings()


def r2_s3_endpoint_url(settings: Optional[Settings] = None) -> str:
    s = settings or get_settings()
    account = (s.r2_account_id or "").strip()
    if not account:
        return ""
    return f"https://{account}.r2.cloudflarestorage.com"
