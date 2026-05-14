"""Stable string codes for fail-closed OpenAI canary checks (ops logs, tests, support)."""

from __future__ import annotations

from enum import Enum


class CanaryFailClosedCode(str, Enum):
    """Raised via :class:`ai.provider_mode.ProviderDisabledError` messages as ``[code] …``."""

    KILL_SWITCH_OFF = "ai_canary_kill_switch_off"
    NUMERIC_CAPS_INVALID = "ai_canary_numeric_caps_invalid"
    AI_PROVIDER_NOT_OPENAI = "ai_canary_ai_provider_not_openai"
    OPENAI_API_KEY_MISSING = "ai_canary_openai_api_key_missing"
    STRUCTURED_MODE_NOT_CANARY = "ai_canary_structured_mode_not_canary"
    CANARY_RUNNER_FLAG_OFF = "ai_canary_runner_flag_off"


class CanaryRuntimeCode(str, Enum):
    """Non-gate failures after gates pass (HTTP transport, parsing, or legacy shell)."""

    ADAPTER_HTTP_NOT_WIRED = "openai_canary_adapter_http_not_wired"
    HTTP_AUTH = "openai_canary_http_auth"
    HTTP_RATE_LIMIT = "openai_canary_http_rate_limit"
    HTTP_BAD_REQUEST = "openai_canary_http_bad_request"
    HTTP_SERVER = "openai_canary_http_server_error"
    HTTP_TIMEOUT = "openai_canary_http_timeout"
    HTTP_MALFORMED = "openai_canary_http_malformed_response"
    HTTP_NETWORK = "openai_canary_http_network"
    SCHEMA_NOT_REGISTERED = "openai_canary_schema_not_registered"
