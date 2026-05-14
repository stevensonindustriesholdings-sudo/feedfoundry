"""Typed request/response objects for the Phase 7 structured AI worker layer.

These are transport shapes for ``AIProvider.complete`` — not Pydantic output schemas
for factsheets/FAQs (those arrive in a later slice).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class AICompletionRequest:
    """Single bounded LLM call metadata (every call must be named and traced)."""

    stage_name: str
    schema_name: str
    schema_version: str
    prompt_version: str
    model: str
    input_bundle: Mapping[str, Any]
    max_tokens: int
    temperature: float
    timeout_seconds: int
    cost_cap: float
    trace_id: str


@dataclass
class AICompletionResponse:
    """Provider result after local JSON parsing (adapter responsibility)."""

    parsed_json: dict[str, Any]
    raw_text: Optional[str]
    input_tokens: int
    output_tokens: int
    cost_estimate: float
    latency_ms: int
    provider_request_id: str
    finish_reason: str
    provider_name: str
    retry_count: int = 0
    raw_response_meta: dict[str, Any] = field(default_factory=dict)
