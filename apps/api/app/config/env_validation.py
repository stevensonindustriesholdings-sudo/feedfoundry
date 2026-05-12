"""
Central environment validation for API and worker.

Strict tiers: ``production`` / ``prod`` / ``staging`` require real credentials.
``development`` / ``local`` / ``test`` allow safe placeholders for local work.
"""

from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.settings import Settings, r2_s3_endpoint_url

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "replace_me",
        "sk_test_replace_me",
        "whsec_replace_me",
        "price_replace_me",
    }
)


def _stripped(value: str | None) -> str:
    return (value or "").strip()


def _is_placeholder(value: str | None) -> bool:
    v = _stripped(value).lower()
    return v in _PLACEHOLDER_KEYS or v.startswith("replace_me")


def is_strict_deployment_env(app_env: str) -> bool:
    return _stripped(app_env).lower() in ("production", "prod", "staging")


def is_production_env(app_env: str) -> bool:
    return _stripped(app_env).lower() in ("production", "prod")


def _r2_configured(settings: Settings) -> bool:
    if not r2_s3_endpoint_url(settings):
        return False
    if _is_placeholder(settings.r2_access_key_id) or _is_placeholder(settings.r2_secret_access_key):
        return False
    if not _stripped(settings.r2_bucket_source) or not _stripped(settings.r2_bucket_outputs):
        return False
    return True


def _stripe_configured(settings: Settings) -> bool:
    return not _is_placeholder(settings.stripe_secret_key) and not _is_placeholder(
        settings.stripe_webhook_secret
    )


def collect_readiness(settings: Settings) -> dict[str, Any]:
    """
    Non-throwing readiness snapshot for GET /ready.
    Does not perform R2 object I/O (only config presence).
    """
    checks: dict[str, dict[str, Any]] = {}
    strict = is_strict_deployment_env(settings.app_env)

    # Database
    db_ok = False
    db_detail = "not_checked"
    try:
        from app.db import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "connected"
    except SQLAlchemyError as e:
        db_detail = f"error:{type(e).__name__}"
    except Exception as e:
        db_detail = f"error:{type(e).__name__}"

    checks["database"] = {"ready": db_ok, "detail": db_detail}

    # Required env presence (no secret values)
    checks["app"] = {
        "ready": bool(_stripped(settings.app_name)),
        "app_env": settings.app_env,
        "public_api_base_url_configured": bool(_stripped(settings.public_api_base_url)),
    }

    ff_ok = bool(_stripped(settings.ff_internal_api_key))
    if strict:
        ff_ok = ff_ok and not _is_placeholder(settings.ff_internal_api_key)
    checks["internal_api"] = {
        "ready": ff_ok,
        "detail": "missing_or_placeholder" if not ff_ok else "ok",
    }

    r2_ready = _r2_configured(settings)
    checks["r2"] = {
        "ready": r2_ready if strict else True,  # dev: not required for process to boot
        "configured": r2_ready,
        "detail": "full_credentials_required_in_strict_env" if strict and not r2_ready else "ok",
    }

    stripe_ready = _stripe_configured(settings)
    checks["stripe"] = {
        "ready": stripe_ready if strict else True,
        "configured": stripe_ready,
        "detail": "keys_required_in_strict_env" if strict and not stripe_ready else "optional_in_dev",
    }

    checks["worker_settings"] = {
        "ready": True,
        "poll_interval_seconds": settings.worker_poll_interval_seconds,
    }

    checks["ai_providers"] = {
        "ready": True,
        "note": "optional until AI pipeline is wired",
        "openai_key_present": bool(_stripped(os.environ.get("OPENAI_API_KEY", ""))),
    }

    overall = db_ok and ff_ok
    if strict:
        overall = overall and r2_ready and stripe_ready

    return {
        "ready": overall,
        "environment": settings.app_env,
        "strict_validation": strict,
        "checks": checks,
    }


def validate_settings_for_startup(settings: Settings) -> None:
    """
    Fail fast on API startup when strict env is missing critical configuration.

    Raises:
        ValueError: with human-readable bullet list of problems.
    """
    errors: list[str] = []

    if not _stripped(settings.database_url):
        errors.append("DATABASE_URL is required")

    if not _stripped(settings.ff_internal_api_key):
        errors.append("FF_INTERNAL_API_KEY is required")

    if is_strict_deployment_env(settings.app_env):
        if _is_placeholder(settings.ff_internal_api_key):
            errors.append(
                "FF_INTERNAL_API_KEY must not be a placeholder value in staging/production",
            )
        if not _stripped(settings.public_api_base_url):
            errors.append("PUBLIC_API_BASE_URL is required in staging/production")
        if not _r2_configured(settings):
            errors.append(
                "R2/S3 storage is not fully configured "
                "(R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, buckets)",
            )
        if not _stripe_configured(settings):
            errors.append("STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are required in staging/production")

    if is_production_env(settings.app_env):
        if not re.match(r"^https://", _stripped(settings.public_api_base_url), re.I):
            errors.append("PUBLIC_API_BASE_URL should use https in production")

    if errors:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))


def validate_worker_environment(settings: Settings) -> None:
    """
    Worker process startup validation (stricter in staging/production).
    """
    errors: list[str] = []
    if not _stripped(settings.database_url):
        errors.append("DATABASE_URL is required for worker")

    if is_strict_deployment_env(settings.app_env):
        if not _r2_configured(settings):
            errors.append("Worker requires full R2 credentials in staging/production (writes outputs)")
        if _is_placeholder(settings.ff_internal_api_key):
            errors.append("FF_INTERNAL_API_KEY must be set for worker in strict environments")

    if errors:
        raise ValueError("Worker configuration error:\n- " + "\n- ".join(errors))
