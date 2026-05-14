"""Extra coverage for Phase 7 worker ``ai`` skeleton (no network, no provider SDKs)."""

from __future__ import annotations

import pytest

from ai.captain import AICaptain
from ai.chunking import chunk_transcript_text
from ai.mock_provider import MockAIProvider, deterministic_stub_bundle
from ai.types import AICompletionRequest


def test_chunking_overlap_zero_allowed():
    parts = chunk_transcript_text("abcd", max_chars=2, overlap=0)
    assert [(a, b) for a, b, _ in parts] == [(0, 2), (2, 4)]


def test_chunking_raises_on_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_transcript_text("abc", max_chars=3, overlap=3)
    with pytest.raises(ValueError):
        chunk_transcript_text("abc", max_chars=3, overlap=-1)
    with pytest.raises(ValueError):
        chunk_transcript_text("abc", max_chars=0, overlap=0)


def test_chunking_single_window():
    assert chunk_transcript_text("hi", max_chars=10, overlap=0) == [(0, 2, "hi")]


def test_mock_provider_echo_keys_sorted():
    p = MockAIProvider()
    req = AICompletionRequest(
        stage_name="visual_analyst",
        schema_name="ai.stub.v1",
        schema_version="0.1.0",
        prompt_version="pv",
        model="mock",
        input_bundle={"z": 1, "a": 2},
        max_tokens=32,
        temperature=0.0,
        timeout_seconds=5,
        cost_cap=0.0,
        trace_id="job:x:visual",
    )
    out = p.complete(req)
    assert out.parsed_json["echo_keys"] == ["a", "z"]


def test_captain_respects_explicit_mock_provider():
    mock = MockAIProvider()
    cap = AICaptain(provider=mock)
    assert cap.provider is mock
    assert len(cap.run_plan(job_id="j1", input_bundle={})) == 6


def test_deterministic_stub_bundle_keys():
    b = dict(deterministic_stub_bundle("any"))
    assert "stage" in b and "note" in b
