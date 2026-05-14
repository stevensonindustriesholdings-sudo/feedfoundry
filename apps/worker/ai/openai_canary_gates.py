"""Central fail-closed checks for structured OpenAI canary (registry + adapter shell)."""

from __future__ import annotations

import os

from ai.canary_error_codes import CanaryFailClosedCode
from ai.provider_mode import ProviderDisabledError, StructuredProviderMode, resolve_structured_provider_mode
from app.services.ai_internal_policy import (
    ai_canary_booleans_allow_real_path,
    ai_canary_numeric_gates_satisfied,
    ai_provider_allows_openai_structured_path,
    load_ai_canary_gate_config_from_env,
)


def _openai_key_present() -> bool:
    key = os.environ.get("OPENAI_API_KEY")
    return bool(key and key.strip())


def _truthy_env(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def openai_canary_runner_env_enabled() -> bool:
    """Mirror ``FF_OPENAI_CANARY_RUNNER_ENABLED`` without importing ``canary_runner`` (import cycle)."""

    return _truthy_env(os.environ.get("FF_OPENAI_CANARY_RUNNER_ENABLED"))


def worker_enrichment_openai_http_env_enabled() -> bool:
    """Allow ``POST …/v1/responses`` from worker transcript enrichment (no import cycle)."""

    return _truthy_env(os.environ.get("FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE"))


def check_openai_structured_canary_gates_or_raise() -> None:
    """Validate env/policy for structured OpenAI canary booleans, numerics, provider, key."""

    cfg = load_ai_canary_gate_config_from_env()
    if not ai_canary_booleans_allow_real_path(cfg):
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.KILL_SWITCH_OFF.value}] Structured OpenAI canary requires "
            "AI_CANARY_ENABLED=true and AI_ENABLE_REAL_PROVIDER=true."
        )
    if not ai_canary_numeric_gates_satisfied(cfg):
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.NUMERIC_CAPS_INVALID.value}] Structured OpenAI canary requires "
            "AI_CANARY_MAX_CALLS>=1, AI_CANARY_MAX_COST>0, and AI_CANARY_TIMEOUT_SECONDS>=1."
        )
    if not ai_provider_allows_openai_structured_path():
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.AI_PROVIDER_NOT_OPENAI.value}] Structured OpenAI canary requires "
            "AI_PROVIDER=openai."
        )
    if not _openai_key_present():
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.OPENAI_API_KEY_MISSING.value}] Structured OpenAI canary requires "
            "a non-empty OPENAI_API_KEY in the worker environment."
        )


def check_openai_structured_adapter_construct_gates_or_raise() -> None:
    """Gates for instantiating :class:`ai.openai_adapter.OpenAIStructuredProviderShell` (no HTTP yet)."""

    check_openai_structured_canary_gates_or_raise()
    if resolve_structured_provider_mode() != StructuredProviderMode.CANARY_OPENAI:
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.STRUCTURED_MODE_NOT_CANARY.value}] Structured OpenAI canary requires "
            "AI_STRUCTURED_PROVIDER_MODE=canary_openai (legacy alias: canary)."
        )


def check_openai_responses_http_gates_or_raise() -> None:
    """All gates required before a live ``POST .../v1/responses`` (canary runner and/or worker enrichment)."""

    check_openai_structured_adapter_construct_gates_or_raise()
    if not openai_canary_runner_env_enabled() and not worker_enrichment_openai_http_env_enabled():
        raise ProviderDisabledError(
            f"[{CanaryFailClosedCode.CANARY_RUNNER_FLAG_OFF.value}] Structured OpenAI HTTP requires "
            "FF_OPENAI_CANARY_RUNNER_ENABLED=true and/or FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE=true."
        )
