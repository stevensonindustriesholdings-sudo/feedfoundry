from __future__ import annotations

from pipeline.transcript import (
    StubTranscriptProvider,
    TranscriptPipelineInput,
    build_transcript_stub_payload,
    run_transcript_pipeline_v0,
    select_transcript_provider,
)


def test_transcript_stub_payload_shape():
    inp = TranscriptPipelineInput(
        job_id="job_test",
        media_asset_id="ma_test",
        audio_wav_path=None,
        audio_extraction={
            "schema_version": "1.0",
            "source_duration_seconds": 2.5,
            "has_audio_stream": False,
            "success": True,
            "skipped_reason": "no_audio_stream",
        },
        media_inspection={"duration_seconds": 2.5},
    )
    doc = build_transcript_stub_payload(inp, source="transcript_stub")
    assert doc["schema_version"] == "1.0"
    assert doc["source"] == "transcript_stub"
    assert "audio_extraction" in doc
    assert doc["audio_extraction"]["skipped_reason"] == "no_audio_stream"
    assert isinstance(doc["segments"], list)
    assert doc["segments"][0]["start"] == 0.0
    assert "job_test" in doc["segments"][0]["text"]


def test_select_provider_stub_without_key():
    p = select_transcript_provider(openai_api_key="")
    assert p.name == "transcript_stub"


def test_select_provider_openai_when_key_set():
    p = select_transcript_provider(openai_api_key="sk-not-a-real-key-for-unit-test")
    assert p.name == "openai_whisper"


def test_run_transcript_pipeline_v0_stub():
    inp = TranscriptPipelineInput(
        job_id="job_x",
        media_asset_id="ma_x",
        audio_wav_path=None,
        audio_extraction={"schema_version": "1.0", "success": True, "has_audio_stream": False},
        media_inspection=None,
    )
    out = run_transcript_pipeline_v0(inp, openai_api_key="")
    assert out["source"] == "transcript_stub"


def test_stub_provider_protocol():
    inp = TranscriptPipelineInput(
        job_id="j",
        media_asset_id="m",
        audio_wav_path=None,
        audio_extraction={"schema_version": "1.0", "success": True},
        media_inspection={"duration_seconds": 1.0},
    )
    doc = StubTranscriptProvider().transcribe(inp)
    assert "segments" in doc
