"""Root-level observability: liveness, readiness, version (Railway / load balancers)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response

from app.config.env_validation import collect_readiness
from app.settings import get_settings

router = APIRouter(tags=["observability"])


@router.get("/health")
def health_live() -> dict[str, Any]:
    """Liveness only — no database or external I/O."""
    return {
        "status": "ok",
        "service": "feedfoundry-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
def readiness(response: Response) -> dict[str, Any]:
    """
    Readiness snapshot: database connectivity, required env tier, R2/Stripe presence.
    Returns HTTP 503 when ``ready`` is false (for orchestrators that honor status codes).
    """
    settings = get_settings()
    body = collect_readiness(settings)
    if not body.get("ready"):
        response.status_code = 503
    return body


@router.get("/version")
def version_info() -> dict[str, Any]:
    s = get_settings()
    return {
        "app_name": s.app_name,
        "app_env": s.app_env,
        "api_version": s.api_version,
        "git_commit": _stripped(s.git_commit) or os.environ.get("GIT_COMMIT", ""),
        "build_timestamp": _stripped(s.build_timestamp) or os.environ.get("BUILD_TIMESTAMP", ""),
    }


def _stripped(v: str) -> str:
    return (v or "").strip()
