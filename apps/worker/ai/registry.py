"""Select structured AI provider from environment (mock-first, canary-gated)."""

from __future__ import annotations

from ai.disabled_provider import DisabledStructuredProvider
from ai.mock_provider import MockAIProvider
from ai.openai_adapter import OpenAIStructuredProviderShell
from ai.openai_canary_gates import check_openai_structured_canary_gates_or_raise
from ai.provider import AIProvider
from ai.provider_mode import StructuredProviderMode, resolve_structured_provider_mode


def get_structured_ai_provider() -> AIProvider:
    """Return the Phase 7 structured AI provider.

    **Modes** — see ``ai.provider_mode`` and ``docs/phase7-openai-canary.md``:

    - ``mock`` (default): :class:`ai.mock_provider.MockAIProvider` only.
    - ``disabled``: :class:`ai.disabled_provider.DisabledStructuredProvider`.
    - ``canary_openai`` (legacy env ``canary``):
      :class:`ai.openai_adapter.OpenAIStructuredProviderShell` **only** when
      kill-switch booleans, numeric caps, ``AI_PROVIDER=openai``, and ``OPENAI_API_KEY``
      are satisfied; otherwise raises :class:`ai.provider_mode.ProviderDisabledError`
      (fail-closed; no silent mock). The adapter constructor re-checks the same gates.
    """
    mode = resolve_structured_provider_mode()

    if mode == StructuredProviderMode.MOCK:
        return MockAIProvider()
    if mode == StructuredProviderMode.DISABLED:
        return DisabledStructuredProvider()
    check_openai_structured_canary_gates_or_raise()
    return OpenAIStructuredProviderShell()
