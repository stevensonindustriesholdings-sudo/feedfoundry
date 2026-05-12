from __future__ import annotations

import time

from providers.base import BaseProvider, ProviderResult


class MistralProvider(BaseProvider):
    name = "mistral"

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
        _ = (model, system, user, max_output_tokens, temperature, timeout_seconds)
        started = time.perf_counter()
        return ProviderResult(
            text="",
            input_tokens_estimated=0,
            output_tokens_estimated=0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw_response_meta={"stub": True},
        )
