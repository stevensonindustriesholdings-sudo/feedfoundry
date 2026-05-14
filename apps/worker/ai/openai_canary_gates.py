"""Central fail-closed checks for structured OpenAI canary (registry + adapter shell)."""

from __future__ import annotations

import os

from ai.canary_error_codes import CanaryFailClosedCode
from ai.provider_mode import ProviderDisabledError
from app.services.ai_internal_policy import (
    ai_canary_booleans_allow_real_path,
    ai_canary_numeric_gates_satisfied,
    ai_provider_allows_openai_structured_path,
    load_ai_canary_gate_config_from_env,
)


def _openai_key_present() -> bool:
    key = os.environ.get("OPENAI_API_KEY")
    return bool(key and key.strip())


def check_openai_structured_canary_gates_or_raise() -> None:
    """Validate env/policy for ``OpenAIStructuredProviderShell``; raise :class:`ProviderDisabledError` if blocked."""

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
