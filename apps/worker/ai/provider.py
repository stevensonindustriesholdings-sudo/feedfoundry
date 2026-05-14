"""Abstract AI provider for structured Phase 7 worker calls."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ai.types import AICompletionRequest, AICompletionResponse


class AIProvider(ABC):
    """Provider adapter: one ``complete`` entrypoint; implementations hide SDK quirks."""

    name: str

    @abstractmethod
    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """Execute a single bounded completion; must not perform unbounded retries."""
