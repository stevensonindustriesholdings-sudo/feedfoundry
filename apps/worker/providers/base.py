from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ProviderResult:
    text: str
    input_tokens_estimated: int
    output_tokens_estimated: int
    latency_ms: int
    raw_response_meta: Optional[dict[str, Any]] = None


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def complete_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_output_tokens: int,
        temperature: float,
        timeout_seconds: int,
    ) -> ProviderResult:
        raise NotImplementedError
