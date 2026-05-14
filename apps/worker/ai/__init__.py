"""Phase 7 structured AI worker layer (orchestrator, mock provider, module stubs).

This package is **parallel** to ``apps/worker/providers/*`` (YAML text completions).
New intelligence pipelines should call through ``AIProvider`` + ``AICaptain`` here
once wired; existing pipelines remain unchanged until migrated.
"""

from ai.captain import AICaptain
from ai.mock_provider import MockAIProvider
from ai.provider import AIProvider
from ai.registry import get_structured_ai_provider
from ai.types import AICompletionRequest, AICompletionResponse

__all__ = [
    "AICompletionRequest",
    "AICompletionResponse",
    "AIProvider",
    "AICaptain",
    "MockAIProvider",
    "get_structured_ai_provider",
]
