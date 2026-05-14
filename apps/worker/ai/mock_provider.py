"""Deterministic mock provider for CI and local development (no network)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Mapping

from ai.provider import AIProvider
from ai.types import AICompletionRequest, AICompletionResponse


class MockAIProvider(AIProvider):
    """Returns stable JSON payloads derived from ``stage_name`` / ``schema_name`` only."""

    name = "mock"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        t0 = time.perf_counter()
        payload: dict[str, Any] = {
            "schema_version": request.schema_version,
            "stage": request.stage_name,
            "schema": request.schema_name,
            "echo_keys": sorted(str(k) for k in request.input_bundle.keys()),
            "provider": self.name,
            "trace_id": request.trace_id,
        }
        raw = json.dumps(payload, sort_keys=True)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return AICompletionResponse(
            parsed_json=payload,
            raw_text=raw,
            input_tokens=1,
            output_tokens=len(raw) // 4,
            cost_estimate=0.0,
            latency_ms=max(latency_ms, 0),
            provider_request_id=f"mock-{uuid.uuid4()}",
            finish_reason="stop",
            provider_name=self.name,
            retry_count=0,
            raw_response_meta={"mock": True},
        )


def deterministic_stub_bundle(stage: str) -> Mapping[str, Any]:
    """Tiny fixture bundle for tests (no secrets, no PII)."""
    return {"stage": stage, "note": "stub"}
