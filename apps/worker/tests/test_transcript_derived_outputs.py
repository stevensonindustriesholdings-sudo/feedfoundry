from __future__ import annotations

from pipeline.transcript_derived_outputs import (
    build_chapters_from_transcript,
    build_ctas_from_transcript,
    build_fact_sheet_from_transcript,
    build_faqs_from_transcript,
    build_hosted_manifest_from_transcript,
    build_metadata_from_transcript,
    derived_from_for_transcript,
)


def _sample_transcript_stub() -> dict:
    return {
        "schema_version": "1.0",
        "source": "transcript_stub",
        "audio_extraction": {"has_audio": True},
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Welcome back. Today we discuss feed routing and archive storage."},
            {"start": 2.5, "end": 5.0, "text": "Second beat: deterministic outputs without an LLM."},
        ],
    }


def _sample_media_inspection() -> dict:
    return {
        "duration_seconds": 12.5,
        "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
        "video_codec": "h264",
        "audio_codec": "aac",
        "file_size_bytes": 4096,
    }


def test_derived_from_openai_vs_stub() -> None:
    stub = _sample_transcript_stub()
    assert derived_from_for_transcript(stub) == "transcript_stub"
    assert derived_from_for_transcript({**stub, "source": "openai_whisper"}) == "openai_whisper"


def test_chapters_shape_and_content() -> None:
    tr = _sample_transcript_stub()
    out = build_chapters_from_transcript(tr, _sample_media_inspection(), derived_from="transcript_stub")
    assert out["schema_version"] == "1.0"
    assert out["derived_from"] == "transcript_stub"
    assert len(out["chapters"]) == 2
    assert "welcome" in out["chapters"][0]["title"].lower()
    assert out["chapters"][0]["start_seconds"] == 0.0
    assert "feed routing" in out["chapters"][0]["summary"].lower()


def test_fact_sheet_statements_from_transcript() -> None:
    tr = _sample_transcript_stub()
    out = build_fact_sheet_from_transcript(tr, None, derived_from="transcript_stub")
    assert out["derived_from"] == "transcript_stub"
    assert len(out["facts"]) >= 1
    joined = " ".join(f["statement"] for f in out["facts"])
    assert "archive" in joined.lower() or "deterministic" in joined.lower()


def test_faqs_include_duration_when_inspection_present() -> None:
    tr = _sample_transcript_stub()
    mi = _sample_media_inspection()
    out = build_faqs_from_transcript(tr, mi, derived_from="transcript_stub")
    assert out["derived_from"] == "transcript_stub"
    questions = [f["question"] for f in out["faqs"]]
    assert any("long" in q.lower() for q in questions)
    joined = " ".join(f["answer"] for f in out["faqs"]).lower()
    assert "transcript_stub" not in joined
    assert "paid ai" not in joined


def test_metadata_technical_block() -> None:
    tr = _sample_transcript_stub()
    out = build_metadata_from_transcript(tr, _sample_media_inspection(), derived_from="transcript_stub", original_basename="demo_episode.mp4")
    assert out["derived_from"] == "transcript_stub"
    assert out["technical"]["video_codec"] == "h264"
    assert out["transcript"]["segment_count"] == 2
    assert out["transcript"]["origin"] == "preview_from_upload"
    assert out["episode"]["display_title"]
    assert isinstance(out["tags"], list) and out["tags"]


def test_hosted_manifest_lists_outputs_and_meta() -> None:
    tr = _sample_transcript_stub()
    mi = _sample_media_inspection()
    planned = [
        "raw_transcript",
        "chapters",
        "fact_sheet",
        "faqs",
        "metadata",
        "ctas",
        "hosted_manifest",
        "media_inspection",
        "export_bundle",
    ]
    out = build_hosted_manifest_from_transcript(
        transcript=tr,
        media_inspection=mi,
        creator_slug="acme",
        asset_slug="ep-42",
        original_basename="clip.mp4",
        outputs_available=planned,
        derived_from="transcript_stub",
    )
    assert out["creator_slug"] == "acme"
    assert out["asset_slug"] == "ep-42"
    assert out["outputs_available"] == planned
    assert out["derived_from"] == "transcript_stub"
    assert out["transcript_meta"]["segment_count"] == 2
    assert out["transcript_meta"]["source"] == "preview_from_upload"
    assert "combined_preview" not in out["transcript_meta"]
    assert len(out["chapters"]) >= 1
    assert isinstance(out["topics"], list) and out["topics"]
    assert len(out["facts"]) >= 1
    assert len(out["faqs"]) >= 1
    assert "seo" in out and out["seo"].get("meta_title")
    assert out["ctas"] and out["ctas"][0].get("intent") == "read_transcript"
    assert any(c.get("intent") == "view_chapters" for c in out["ctas"])


def test_ctas_document_shape() -> None:
    tr = _sample_transcript_stub()
    out = build_ctas_from_transcript(tr, _sample_media_inspection(), derived_from="transcript_stub")
    assert out["schema_version"] == "1.0"
    assert out["derived_from"] == "transcript_stub"
    assert isinstance(out["ctas"], list) and len(out["ctas"]) >= 2
    assert {c["intent"] for c in out["ctas"]} >= {"read_transcript", "share_episode"}
    tr = {
        "schema_version": "1.0",
        "source": "transcript_stub",
        "segments": [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "transcript_stub_v0 job=j1 media=m1 (no external ASR) Real episode content starts here.",
            }
        ],
    }
    out = build_chapters_from_transcript(tr, None, derived_from="transcript_stub")
    title = out["chapters"][0]["title"].lower()
    assert "transcript_stub_v0" not in title
    assert "real episode" in title or "content" in title
