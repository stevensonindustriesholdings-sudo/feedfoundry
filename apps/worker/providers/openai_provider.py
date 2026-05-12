from __future__ import annotations

import os
import time

from providers.base import BaseProvider, ProviderResult


class OpenAIProvider(BaseProvider):
    name = "openai"

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
        _ = (system, user, max_output_tokens, temperature, timeout_seconds)
        if not os.environ.get("OPENAI_API_KEY"):
            return ProviderResult(
                text="",
                input_tokens_estimated=0,
                output_tokens_estimated=0,
                latency_ms=0,
                raw_response_meta={"error": "OPENAI_API_KEY not set"},
            )
        # Implement with openai SDK in a follow-up; router enforces budgets.
        started = time.perf_counter()
        time.sleep(0)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            text="",
            input_tokens_estimated=0,
            output_tokens_estimated=0,
            latency_ms=latency_ms,
            raw_response_meta={"note": "stub"},
        )
