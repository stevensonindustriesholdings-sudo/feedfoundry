"""Select structured AI provider from environment (mock-first)."""

from __future__ import annotations

import os

from ai.mock_provider import MockAIProvider
from ai.provider import AIProvider


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def get_structured_ai_provider() -> AIProvider:
    """Return the Phase 7 structured AI provider.

    Default: mock provider (no network, no API keys). Real adapters are added in a
    later slice; until then, disabling mock without wiring raises ``NotImplementedError``.
    """
    if _truthy(os.environ.get("AI_ENABLE_MOCK_PROVIDER", "true")):
        return MockAIProvider()
    raise NotImplementedError(
        "Structured real AI providers are not wired in this repo slice; "
        "set AI_ENABLE_MOCK_PROVIDER=true for tests/dev or implement adapters first."
    )
