"""OpenAI structured provider adapter — **canary shell only** (no HTTP in this slice).

No third-party SDK imports at module load. :meth:`OpenAIStructuredProviderShell.complete`
raises until a later sprint wires a bounded client (lazy SDK import will live there).
"""

from __future__ import annotations

from ai.provider import AIProvider
from ai.types import AICompletionRequest, AICompletionResponse


class OpenAIStructuredProviderShell(AIProvider):
    """Gated shell; construction does not touch the network."""

    name = "openai"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        raise RuntimeError(
            "OpenAI structured canary adapter is a shell in this repo slice "
            "(no live HTTP); wire SDK only under an explicit canary sprint."
        )
