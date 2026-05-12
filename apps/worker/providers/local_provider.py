from __future__ import annotations

import time

from providers.base import BaseProvider, ProviderResult


class LocalProvider(BaseProvider):
    name = "local"

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
        _ = (model, max_output_tokens, temperature, timeout_seconds)
        started = time.perf_counter()
        text = f"[local:{model}] {user[:200]}"
        return ProviderResult(
            text=text,
            input_tokens_estimated=len(user) // 4,
            output_tokens_estimated=len(text) // 4,
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw_response_meta={"stub": True, "system_preview": system[:80]},
        )
