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

    # Optional OpenAI (worker transcript v0 — Whisper); leave unset to use transcript_stub
    openai_api_key: str = ""

    # Worker-related (API logs readiness; worker reads same env names)
    worker_poll_interval_seconds: int = 5
    storage_provider: str = "r2"
    # Cloudflare R2: set R2_ACCOUNT_ID and the endpoint is constructed automatically.
    # Generic S3-compatible storage (e.g. Railway buckets): set R2_ENDPOINT_URL directly.
    # Only one of R2_ACCOUNT_ID or R2_ENDPOINT_URL is required; R2_ENDPOINT_URL takes precedence.
    r2_account_id: str = ""
    r2_endpoint_url: str = ""
    r2_region: str = "auto"
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    # In staging, r2_bucket_source and r2_bucket_outputs may reference the same bucket.
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
    """Resolve the S3-compatible endpoint URL for storage.

    Resolution order:
    1. ``R2_ENDPOINT_URL`` — explicit endpoint for generic S3-compatible storage
       (e.g. Railway buckets).  Takes precedence when set and non-empty.
    2. ``R2_ACCOUNT_ID`` — constructs the Cloudflare R2 endpoint automatically
       (``https://<account>.r2.cloudflarestorage.com``).
    3. Neither set → returns ``""`` (storage not configured).
    """
    s = settings or get_settings()
    explicit = (s.r2_endpoint_url or "").strip()
    if explicit:
        return explicit
    account = (s.r2_account_id or "").strip()
    if account:
        return f"https://{account}.r2.cloudflarestorage.com"
    return ""
