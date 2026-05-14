"""Transcript intelligence: fixtures + validation/evidence (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.mock_provider import MockAIProvider
from ai.modules.output_validator import OutputValidator, ValidationStatus
from ai.modules.transcript_intelligence import (
    STAGE_NAME,
    TranscriptIntelligenceValidationError,
    chunks_from_plain_text,
    iter_accepted_models,
    run_transcript_intelligence,
)
from ai.provider import AIProvider
from ai.schemas.output_contracts import FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION
from ai.transcript_context import TranscriptChunkInput
from ai.types import AICompletionRequest, AICompletionResponse


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_chunk_to_validated_outputs_roundtrip():
    text = "alpha beta gamma " * 20
    chunks = chunks_from_plain_text(text, max_chars=40, overlap=8)
    assert len(chunks) >= 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    arts = run_transcript_intelligence(chunks, job_id="job-fixture-1")
    assert len(arts) == len(chunks) * 4
    models = iter_accepted_models(arts)
    assert len(models) == len(arts)
    for a in arts:
        assert a.validation.status == ValidationStatus.ACCEPTED
        assert 0 <= a.evidence.chunk_index < len(chunks)


def test_provenance_segment_times_in_evidence():
    chunks = [
        TranscriptChunkInput(chunk_index=0, text="hello world", segment_id="seg-a", start_ms=0, end_ms=1200),
        TranscriptChunkInput(chunk_index=1, text="second window", segment_id="seg-b", start_ms=1200, end_ms=2400),
    ]
    arts = run_transcript_intelligence(chunks, job_id="job-prov-1")
    by_chunk: dict[int, list] = {}
    for a in arts:
        by_chunk.setdefault(a.evidence.chunk_index, []).append(a)
    assert by_chunk[0][0].evidence.segment_id == "seg-a"
    assert by_chunk[0][0].evidence.start_ms == 0
    assert by_chunk[1][0].evidence.segment_id == "seg-b"


def test_mock_registry_payload_passes_output_validator():
    p = MockAIProvider()
    req = AICompletionRequest(
        stage_name=STAGE_NAME,
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        prompt_version="pv",
        model="mock",
        input_bundle={
            "chunk_index": 2,
            "transcript_text": "deterministic fixture line",
            "segment_id": "s-9",
            "start_ms": 5000,
            "end_ms": 8000,
            "episode_title": "Fixture Episode",
        },
        max_tokens=64,
        temperature=0.0,
        timeout_seconds=5,
        cost_cap=0.0,
        trace_id="job:fixture:mock",
    )
    out = p.complete(req)
    assert "echo_keys" not in out.parsed_json
    v = OutputValidator().validate_payload(
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        payload=out.parsed_json,
    )
    assert v.status == ValidationStatus.ACCEPTED
    assert v.model is not None
    assert "chunk 2" in v.model.title.lower()


def test_malformed_factsheet_fixture_rejected_by_validator():
    raw = (FIXTURES / "transcript_intelligence_malformed_factsheet.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    v = OutputValidator().validate_payload(
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        payload=payload,
    )
    assert v.status == ValidationStatus.REJECTED
    assert v.errors


class _BadFactsheetProvider(AIProvider):
    name = "bad-factsheet"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if request.schema_name == FACTSHEET_SCHEMA_NAME:
            bad = json.loads((FIXTURES / "transcript_intelligence_malformed_factsheet.json").read_text())
            raw = json.dumps(bad)
            return AICompletionResponse(
                parsed_json=bad,
                raw_text=raw,
                input_tokens=1,
                output_tokens=4,
                cost_estimate=0.0,
                latency_ms=0,
                provider_request_id="bad-1",
                finish_reason="stop",
                provider_name=self.name,
            )
        return MockAIProvider().complete(request)


def test_pipeline_raises_on_malformed_provider_payload():
    chunks = [TranscriptChunkInput(chunk_index=0, text="only one chunk")]
    with pytest.raises(TranscriptIntelligenceValidationError):
        run_transcript_intelligence(chunks, job_id="job-bad", provider=_BadFactsheetProvider())


def test_chunk_index_required_and_non_negative():
    with pytest.raises(ValueError):
        TranscriptChunkInput(chunk_index=-1, text="x")
