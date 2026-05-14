"""Resolve structured AI provider **mode** from environment (mock-first, fail-closed).

Explicit modes (``AI_STRUCTURED_PROVIDER_MODE``):

========  ======================================================================
``mock``  Always use :class:`ai.mock_provider.MockAIProvider` (default).
``canary`` Real OpenAI adapter **only** when worker gates + API policy booleans
          and numeric caps all pass; otherwise :func:`ai.registry.get_structured_ai_provider`
          raises ``ProviderDisabledError`` (no silent fallback to mock).
``disabled`` Return :class:`DisabledStructuredProvider` that raises on ``complete()``.
========  ======================================================================

Legacy: if ``AI_STRUCTURED_PROVIDER_MODE`` is unset and ``AI_ENABLE_MOCK_PROVIDER`` is
false, mode resolves to ``disabled`` (matches prior "mock off" intent).
"""

from __future__ import annotations

import os
from enum import Enum


class StructuredProviderMode(str, Enum):
    MOCK = "mock"
    CANARY = "canary"
    DISABLED = "disabled"


class ProviderDisabledError(RuntimeError):
    """Raised when structured real AI is not permitted (canary gates or mode)."""


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def resolve_structured_provider_mode() -> StructuredProviderMode:
    raw = os.environ.get("AI_STRUCTURED_PROVIDER_MODE")
    if raw is not None and raw.strip() != "":
        key = raw.strip().lower()
        try:
            return StructuredProviderMode(key)
        except ValueError as exc:
            raise ProviderDisabledError(
                f"Invalid AI_STRUCTURED_PROVIDER_MODE={raw!r}; "
                "expected mock, canary, or disabled."
            ) from exc
    # Legacy toggle: mock provider env from Phase 7 skeleton
    if _truthy(os.environ.get("AI_ENABLE_MOCK_PROVIDER", "true")):
        return StructuredProviderMode.MOCK
    return StructuredProviderMode.DISABLED
