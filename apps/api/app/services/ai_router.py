from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field


class AIRequestSpec(BaseModel):
    provider: str
    model: str
    module_name: str
    job_id: str
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0, le=2)
    timeout_seconds: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    cost_ceiling_credits: float = Field(ge=0)
    fallback_provider: str
    fallback_model: str


class AIResponseLog(BaseModel):
    provider: str
    model: str
    module_name: str
    job_id: str
    input_tokens_estimated: Optional[int] = None
    output_tokens_reported_or_estimated: Optional[int] = None
    latency_ms: Optional[int] = None
    success: bool
    retry_count: int = 0
    cost_estimate: Optional[float] = None
    rate_limit_headers: Optional[Dict[str, str]] = None


def load_ai_routing(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_request_for_module(
    *,
    routing: dict[str, Any],
    module_name: str,
    job_id: str,
    model_resolver: dict[str, str],
) -> AIRequestSpec:
    modules = routing.get("modules") or {}
    mod = modules.get(module_name) or {}
    primary = mod.get("primary") or {}
    fallback = mod.get("fallback") or {}
    provider = str(primary.get("provider") or "openai")
    model_env = str(primary.get("model_env") or "OPENAI_CHEAP_TEXT_MODEL")
    model = model_resolver.get(model_env) or model_env
    fb_provider = str(fallback.get("provider") or "local")
    fb_env = str(fallback.get("model_env") or "LOCAL_JSON_REPAIR_MODEL")
    fb_model = model_resolver.get(fb_env) or fb_env
    return AIRequestSpec(
        provider=provider,
        model=model,
        module_name=module_name,
        job_id=job_id,
        max_input_tokens=int(mod.get("max_input_tokens") or 8192),
        max_output_tokens=int(mod.get("max_output_tokens") or 4096),
        temperature=float(mod.get("temperature") or 0.2),
        timeout_seconds=int(mod.get("timeout_seconds") or routing.get("global", {}).get("default_timeout_seconds") or 120),
        max_retries=int(mod.get("max_retries") or routing.get("global", {}).get("default_max_retries") or 3),
        cost_ceiling_credits=float(mod.get("cost_ceiling_credits") or mod.get("cost_ceiling_credits_per_media_hour") or 0),
        fallback_provider=fb_provider,
        fallback_model=fb_model,
    )
