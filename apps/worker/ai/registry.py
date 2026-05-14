"""Select structured AI provider from environment (mock-first, canary-gated)."""

from __future__ import annotations

from ai.disabled_provider import DisabledStructuredProvider
from ai.mock_provider import MockAIProvider
from ai.openai_adapter import OpenAIStructuredProviderShell
from ai.openai_canary_gates import check_openai_structured_adapter_construct_gates_or_raise
from ai.provider import AIProvider
from ai.provider_mode import StructuredProviderMode, resolve_structured_provider_mode


def get_structured_ai_provider() -> AIProvider:
    """Return the Phase 7 structured AI provider.

    **Modes** — see ``ai.provider_mode`` and ``docs/phase7-openai-canary.md``:

    - ``mock`` (default): :class:`ai.mock_provider.MockAIProvider` only.
    - ``disabled``: :class:`ai.disabled_provider.DisabledStructuredProvider`.
    - ``canary_openai`` (legacy env ``canary``):
      :class:`ai.openai_adapter.OpenAIStructuredProviderShell` **only** when
      kill-switch booleans, numeric caps, ``AI_PROVIDER=openai``, ``OPENAI_API_KEY``,
      and ``AI_STRUCTURED_PROVIDER_MODE=canary_openai`` are satisfied; otherwise raises
      :class:`ai.provider_mode.ProviderDisabledError` (fail-closed; no silent mock).
      Live ``POST /v1/responses`` runs only when :func:`ai.openai_canary_gates.check_openai_responses_http_gates_or_raise`
      also passes (includes ``FF_OPENAI_CANARY_RUNNER_ENABLED=true``).
    """
    mode = resolve_structured_provider_mode()

    if mode == StructuredProviderMode.MOCK:
        return MockAIProvider()
    if mode == StructuredProviderMode.DISABLED:
        return DisabledStructuredProvider()
    check_openai_structured_adapter_construct_gates_or_raise()
    return OpenAIStructuredProviderShell()
