"""Select structured AI provider from environment (mock-first, canary-gated)."""

from __future__ import annotations

import os

from ai.disabled_provider import DisabledStructuredProvider
from ai.mock_provider import MockAIProvider
from ai.openai_adapter import OpenAIStructuredProviderShell
from ai.provider import AIProvider
from ai.provider_mode import ProviderDisabledError, StructuredProviderMode, resolve_structured_provider_mode

from app.services.ai_internal_policy import (
    ai_canary_booleans_allow_real_path,
    ai_canary_numeric_gates_satisfied,
    load_ai_canary_gate_config_from_env,
)


def _openai_key_present() -> bool:
    key = os.environ.get("OPENAI_API_KEY")
    return bool(key and key.strip())


def get_structured_ai_provider() -> AIProvider:
    """Return the Phase 7 structured AI provider.

    **Modes** — see ``ai.provider_mode`` and ``docs/phase7-openai-canary.md``:

    - ``mock`` (default): :class:`ai.mock_provider.MockAIProvider` only.
    - ``disabled``: :class:`ai.disabled_provider.DisabledStructuredProvider`.
    - ``canary``: :class:`ai.openai_adapter.OpenAIStructuredProviderShell` **only** when
      kill-switch booleans, numeric caps, and ``OPENAI_API_KEY`` are satisfied; otherwise
      raises :class:`ai.provider_mode.ProviderDisabledError` (fail-closed; no silent mock).
    """
    mode = resolve_structured_provider_mode()
    canary_cfg = load_ai_canary_gate_config_from_env()

    if mode == StructuredProviderMode.MOCK:
        return MockAIProvider()
    if mode == StructuredProviderMode.DISABLED:
        return DisabledStructuredProvider()
    # canary
    if not ai_canary_booleans_allow_real_path(canary_cfg):
        raise ProviderDisabledError(
            "Structured canary requires AI_CANARY_ENABLED=true and "
            "AI_ENABLE_REAL_PROVIDER=true (kill-switch)."
        )
    if not ai_canary_numeric_gates_satisfied(canary_cfg):
        raise ProviderDisabledError(
            "Structured canary requires AI_CANARY_MAX_CALLS>=1, "
            "AI_CANARY_MAX_COST>0, and AI_CANARY_TIMEOUT_SECONDS>=1."
        )
    if not _openai_key_present():
        raise ProviderDisabledError(
            "Structured canary requires a non-empty OPENAI_API_KEY in the worker environment."
        )
    return OpenAIStructuredProviderShell()
