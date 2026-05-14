"""Deterministic mock provider for CI and local development (no network)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Mapping

from ai.provider import AIProvider
from ai.schemas.output_contracts import (
    CHAPTERS_SCHEMA_NAME,
    CHAPTERS_SCHEMA_VERSION,
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    FAQ_SCHEMA_NAME,
    FAQ_SCHEMA_VERSION,
    METADATA_SCHEMA_NAME,
    METADATA_SCHEMA_VERSION,
    SCHEMA_REGISTRY,
)
from ai.types import AICompletionRequest, AICompletionResponse


def _bundle_slice(input_bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in input_bundle.items()}


def _deterministic_registry_payload(request: AICompletionRequest) -> dict[str, Any] | None:
    """If *request* targets a registered output contract, return a valid payload dict."""
    key = (request.schema_name, request.schema_version)
    if key not in SCHEMA_REGISTRY:
        return None

    ib = _bundle_slice(request.input_bundle)
    chunk_index = int(ib.get("chunk_index", 0))
    text = str(ib.get("transcript_text", ""))
    summary = text[:500] if text else "No transcript text for this chunk."
    segment_id = ib.get("segment_id")
    start_ms_raw = ib.get("start_ms")
    start_ms = int(start_ms_raw) if start_ms_raw is not None else chunk_index * 60_000

    if key == (FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION):
        title = f"Transcript intelligence facts (chunk {chunk_index})"
        if segment_id is not None:
            title = f"{title} seg={segment_id}"
        key_facts: list[str] = []
        if text.strip():
            toks = text.split()[:5]
            if toks:
                key_facts.append(" ".join(toks) + " …")
        return {"title": title, "summary": summary, "key_facts": key_facts}

    if key == (FAQ_SCHEMA_NAME, FAQ_SCHEMA_VERSION):
        return {
            "items": [
                {
                    "question": f"What is discussed in transcript chunk {chunk_index}?",
                    "answer": summary,
                }
            ]
        }

    if key == (CHAPTERS_SCHEMA_NAME, CHAPTERS_SCHEMA_VERSION):
        return {"chapters": [{"title": f"Chunk {chunk_index}", "start_ms": max(0, start_ms)}]}

    if key == (METADATA_SCHEMA_NAME, METADATA_SCHEMA_VERSION):
        ep = str(ib.get("episode_title") or f"Episode (chunk {chunk_index})")
        tags = [f"chunk:{chunk_index}"]
        if segment_id is not None:
            tags.append(f"segment:{segment_id}")
        return {"episode_title": ep, "speakers": [], "tags": tags}

    # Other registered schemas are not emitted by this mock slice; fall back to echo stub.
    return None


class MockAIProvider(AIProvider):
    """Returns stable JSON payloads derived from ``stage_name`` / ``schema_name`` only."""

    name = "mock"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        t0 = time.perf_counter()
        contract = _deterministic_registry_payload(request)
        if contract is not None:
            payload: dict[str, Any] = contract
        else:
            payload = {
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
