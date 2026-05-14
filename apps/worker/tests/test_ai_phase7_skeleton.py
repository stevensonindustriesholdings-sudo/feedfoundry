from __future__ import annotations

import pytest

from ai.captain import AICaptain
from ai.chunking import chunk_transcript_text
from ai.mock_provider import MockAIProvider, deterministic_stub_bundle
from ai.registry import get_structured_ai_provider
from ai.types import AICompletionRequest


def test_mock_provider_is_deterministic_for_same_stage():
    p = MockAIProvider()
    req = AICompletionRequest(
        stage_name="transcript_intelligence",
        schema_name="ai.stub.v1",
        schema_version="0.1.0",
        prompt_version="t1",
        model="mock",
        input_bundle=dict(deterministic_stub_bundle("transcript_intelligence")),
        max_tokens=64,
        temperature=0.0,
        timeout_seconds=5,
        cost_cap=0.0,
        trace_id="job:test:1",
    )
    a = p.complete(req)
    b = p.complete(req)
    assert a.parsed_json == b.parsed_json
    assert a.provider_name == "mock"
    assert a.finish_reason == "stop"
    # No live provider: request id shape is mock-uuid but differs per call
    assert a.provider_request_id.startswith("mock-")


def test_registry_returns_mock_by_default(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_MOCK_PROVIDER", "true")
    prov = get_structured_ai_provider()
    assert prov.name == "mock"


def test_registry_raises_when_mock_disabled_without_real_adapter(monkeypatch):
    monkeypatch.setenv("AI_ENABLE_MOCK_PROVIDER", "false")
    with pytest.raises(NotImplementedError):
        get_structured_ai_provider()


def test_captain_run_plan_roundtrip():
    cap = AICaptain(provider=MockAIProvider())
    res = cap.run_plan(job_id="job-xyz", input_bundle={"hello": "world"})
    assert len(res) == 6
    stages = [r.parsed_json["stage"] for r in res]
    assert stages == list(cap.default_stages())
    assert all(r.parsed_json["provider"] == "mock" for r in res)


def test_chunking_basic():
    text = "abcdefghijklmnop"
    parts = chunk_transcript_text(text, max_chars=5, overlap=2)
    spans = [(a, b) for a, b, _ in parts]
    assert spans[0] == (0, 5)
    # overlap 2 => next start 3
    assert spans[1][0] == 3

