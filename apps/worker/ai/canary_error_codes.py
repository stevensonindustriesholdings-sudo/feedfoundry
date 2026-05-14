"""Stable string codes for fail-closed OpenAI canary checks (ops logs, tests, support)."""

from __future__ import annotations

from enum import Enum


class CanaryFailClosedCode(str, Enum):
    """Raised via :class:`ai.provider_mode.ProviderDisabledError` messages as ``[code] …``."""

    KILL_SWITCH_OFF = "ai_canary_kill_switch_off"
    NUMERIC_CAPS_INVALID = "ai_canary_numeric_caps_invalid"
    AI_PROVIDER_NOT_OPENAI = "ai_canary_ai_provider_not_openai"
    OPENAI_API_KEY_MISSING = "ai_canary_openai_api_key_missing"


class CanaryRuntimeCode(str, Enum):
    """Non-gate failures after gates pass (e.g. adapter not yet wired to HTTP)."""

    ADAPTER_HTTP_NOT_WIRED = "openai_canary_adapter_http_not_wired"
