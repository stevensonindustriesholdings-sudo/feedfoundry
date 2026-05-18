"""Deterministic visual/evidence squad contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from ai.feedfoundry_agents.visual_evidence.orchestrator import run_visual_evidence_squad

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_visual_evidence" / "tiny_visual_evidence_input.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_keyframes_produce_visual_evidence_package() -> None:
    result = run_visual_evidence_squad(load_fixture())

    assert result["schema_version"] == "0.1"
    assert result["execution_mode"] == "deterministic_mock"
    assert result["media_id"] == "media_demo_001"
    assert result["visual_intelligence"][0]["keyframe_id"] == "kf_0001"
    assert result["visual_intelligence"][0]["timestamp_seconds"] == 12.5
    assert result["visual_intelligence"][0]["frame_uri"].endswith("kf_0001.jpg")
    assert result["visual_intelligence"][0]["visual_summary"]
    assert 0 <= result["visual_intelligence"][0]["confidence_score"] <= 1
    assert result["evidence_gate"]["hosted_manifest_publishability_gate"] in {"hold", "review"}


def test_ocr_placeholder_is_retained_with_confidence_and_pointer() -> None:
    result = run_visual_evidence_squad(load_fixture())
    ocr = result["ocr_text"][0]

    assert ocr["detected_text"] == "Launch checklist: archive, clips, FAQ"
    assert ocr["bounding_region_placeholder"]["shape"] == "full_frame_placeholder"
    assert ocr["confidence_score"] == 0.82
    assert ocr["evidence_pointer"]["keyframe_id"] == "kf_0001"
    assert ocr["evidence_pointer"]["timestamp_seconds"] == 12.5


def test_entities_have_evidence_pointers_and_risk_notes() -> None:
    result = run_visual_evidence_squad(load_fixture())
    entities = result["entities"]

    assert {e["entity_type"] for e in entities} >= {"product", "logo", "person", "object"}
    logo = next(e for e in entities if e["entity_type"] == "logo")
    assert logo["label"] == "FeedFoundry"
    assert logo["evidence_pointer"]["artifact_uri"].endswith("kf_0001.jpg")
    low = next(e for e in entities if e["label"] == "chart")
    assert low["risk_notes"]


def test_transcript_evidence_pointer_supports_at_least_one_claim() -> None:
    result = run_visual_evidence_squad(load_fixture())
    transcript_supported = [e for e in result["transcript_evidence"] if e["claim_supported"]]

    assert transcript_supported
    assert transcript_supported[0]["transcript_chunk_id"] == "tc_001"
    assert transcript_supported[0]["timestamp_range"] == {"start_seconds": 10.0, "end_seconds": 18.0}
    assert "archive clips and FAQs" in transcript_supported[0]["quote_text_excerpt"]


def test_unsupported_claim_is_flagged() -> None:
    result = run_visual_evidence_squad(load_fixture())
    report = result["unsupported_claim_report"]
    revenue = next(item for item in report if "$2M" in item["claim_text"])

    assert revenue["support_status"] == "unsupported"
    assert revenue["missing_evidence_reason"]
    assert revenue["escalation_flag"] is True


def test_low_confidence_visual_or_ocr_evidence_triggers_human_review() -> None:
    result = run_visual_evidence_squad(load_fixture())
    flags = result["escalation_flags"]

    assert flags["low_ocr_confidence"] is True
    assert flags["human_review_required"] is True
    assert result["evidence_gate"]["gate"] in {"hold", "review"}
    assert result["confidence_scores"]["final_evidence_confidence"] < 0.75


def test_no_hosted_manifest_publishability_approval_when_required_evidence_missing() -> None:
    result = run_visual_evidence_squad(load_fixture())
    gate = result["evidence_gate"]

    assert gate["input_hosted_manifest_gate"] == "approve"
    assert gate["hosted_manifest_publishability_gate"] == "hold"
    assert gate["approval_without_evidence_blocked"] is True
    assert "processing_minute_debit_change" not in json.dumps(result).lower()
