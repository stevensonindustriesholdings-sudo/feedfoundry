"""Non-secret processing / worker hints for dashboards (internal key only)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends

from app.auth import verify_internal_key
from app.config.env_validation import _is_placeholder, _stripped
from app.services.ai_router import load_ai_routing
from app.settings import get_settings

router = APIRouter(prefix="/system", tags=["system"])


def _env_truthy(name: str) -> bool:
    return _stripped(os.environ.get(name, "")).lower() in ("1", "true", "yes", "on")


@router.get("/worker-hints")
def worker_hints(_: None = Depends(verify_internal_key)) -> dict[str, Any]:
    """Safe flags for `/system` UI — never returns API keys or tokens."""
    s = get_settings()
    openai_k = _stripped(s.openai_api_key) or _stripped(os.environ.get("OPENAI_API_KEY", ""))
    or_k = _stripped(s.openrouter_api_key) or _stripped(os.environ.get("OPENROUTER_API_KEY", ""))
    routing = load_ai_routing(s.ai_routing_config_path)
    modules = routing.get("modules") or {}
    return {
        "ff_ai_live_calls_enabled": _env_truthy("FF_AI_LIVE_CALLS_ENABLED"),
        "openai_configured": bool(openai_k) and not _is_placeholder(openai_k),
        "openrouter_configured": bool(or_k) and not _is_placeholder(or_k),
        "ai_routing_modules_loaded": len(modules),
        "youtube_source_queue_enabled": True,
        "notes": (
            "Live AI calls require FF_AI_LIVE_CALLS_ENABLED=1 and a configured provider key; "
            "worker logs counts only."
        ),
    }
