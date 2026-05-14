"""Fail-closed provider when structured mode is ``disabled``."""

from __future__ import annotations

from ai.provider import AIProvider
from ai.types import AICompletionRequest, AICompletionResponse


class DisabledStructuredProvider(AIProvider):
    """Structured real path is off; every ``complete`` raises."""

    name = "disabled"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise RuntimeError(
            "Structured AI provider mode is disabled (AI_STRUCTURED_PROVIDER_MODE=disabled "
            "or legacy AI_ENABLE_MOCK_PROVIDER=false)."
        )
