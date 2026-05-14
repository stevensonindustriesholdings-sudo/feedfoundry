from __future__ import annotations

from pipeline.public_payloads import media_inspection_json_for_customer, transcript_json_for_customer


def test_transcript_json_for_customer_strips_internals_and_cleans_text() -> None:
    internal = {
        "schema_version": "1.0",
        "source": "transcript_stub",
        "audio_extraction": {"ffmpeg_command": "ffmpeg -y", "success": True},
        "provider_error": "should_not_appear",
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "transcript_stub_v0 job=j1 media=m1 (no external ASR) Hello world.",
            }
        ],
    }
    pub = transcript_json_for_customer(internal)
    assert pub is not None
    assert "audio_extraction" not in pub
    assert "provider_error" not in pub
    assert pub["source"] == "preview_from_upload"
    assert "transcript_stub_v0" not in pub["segments"][0]["text"]
    assert "hello world" in pub["segments"][0]["text"].lower()


def test_transcript_json_openai_maps_origin() -> None:
    internal = {
        "schema_version": "1.0",
        "source": "openai_whisper",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Hello."}],
    }
    pub = transcript_json_for_customer(internal)
    assert pub is not None
    assert pub["source"] == "automated_speech_to_text"


def test_media_inspection_json_for_customer_drops_chunk_plan() -> None:
    mi = {
        "schema_version": "1.0",
        "duration_seconds": 10.0,
        "chunk_plan": [{"index": 0, "start_sec": 0.0, "end_sec": 10.0}],
    }
    out = media_inspection_json_for_customer(mi)
    assert out is not None
    assert "chunk_plan" not in out
    assert out["duration_seconds"] == 10.0
