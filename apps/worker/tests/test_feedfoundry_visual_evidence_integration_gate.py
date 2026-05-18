"""Visual evidence integration gate for FeedFoundry agent bundle."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from ai.feedfoundry_agents.orchestrator import ENV_VISUAL_EVIDENCE_FLAG, run_feedfoundry_agent_bundle
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"
WORKER_ROOT = Path(__file__).resolve().parents[1]


def _tiny_job() -> FeedFoundryJobInput:
    return FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))


def _passing_job() -> FeedFoundryJobInput:
    return FeedFoundryJobInput.model_validate(
        {
            "job_id": "job_visual_ready",
            "organisation_id": "org_visual_ready",
            "media_asset_id": "media_visual_ready",
            "creator_slug": "fixture-creator",
            "asset_slug": "visual-ready-episode",
            "original_basename": "visual_ready.mp4",
            "transcript": {
                "schema_version": "1.0",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 9.0,
                        "text": "Archive metadata transcript slide explains the launch checklist.",
                    }
                ],
            },
            "visual_frames": [
                {
                    "t_seconds": 2.0,
                    "label": "Archive metadata transcript slide explains the launch checklist",
                    "frame_uri": "artifacts/media_visual_ready/keyframes/kf_0001.jpg",
                }
            ],
            "product_context": {
                "show_name": "Visual Ready Show",
                "niche": "creator_archive_intelligence",
                "primary_topics": ["archive", "metadata", "transcript"],
            },
            "media_meta": {"duration_seconds": 60.0, "container_format": "mp4"},
            "ffmpeg_failure": None,
        }
    )


def test_visual_evidence_flag_defaults_off_preserves_existing_bundle_shape(monkeypatch) -> None:
    monkeypatch.delenv(ENV_VISUAL_EVIDENCE_FLAG, raising=False)
    bundle = run_feedfoundry_agent_bundle(_tiny_job())
    expected = json.loads((FIXTURE_DIR / "expected_bundle_shape.json").read_text(encoding="utf-8"))

    assert set(bundle.model_dump().keys()) == set(expected["top_level_keys"])
    assert not hasattr(bundle, "visual_evidence")
    assert "visual_evidence_squad" not in bundle.run.agents_scheduled


def test_visual_evidence_flag_on_includes_package_and_exposes_status(monkeypatch) -> None:
    monkeypatch.setenv(ENV_VISUAL_EVIDENCE_FLAG, "true")
    bundle = run_feedfoundry_agent_bundle(_tiny_job())

    assert bundle.visual_evidence.evidence_status == "needs_review"
    assert bundle.visual_evidence.visual_evidence_available is True
    assert bundle.visual_evidence.transcript_evidence_available is True
    assert bundle.visual_evidence.unsupported_claim_count >= 1
    assert bundle.visual_evidence.human_review_required is True
    assert bundle.visual_evidence.final_evidence_confidence < 0.75
    assert bundle.visual_evidence.visual_evidence_package_object["agent_id"] == "visual_evidence_squad"
    assert "visual_evidence_squad" in bundle.run.agents_scheduled


def test_unsupported_claim_marks_hosted_geo_and_repository_needs_review(monkeypatch) -> None:
    monkeypatch.setenv(ENV_VISUAL_EVIDENCE_FLAG, "1")
    bundle = run_feedfoundry_agent_bundle(_tiny_job())

    assert bundle.hosted_manifest_hints.evidence_status == "needs_review"
    assert bundle.geo_freshness.evidence_status == "needs_review"
    assert bundle.repository_manifest.evidence_status == "needs_review"
    assert bundle.hosted_manifest_hints.unsupported_claim_count == bundle.visual_evidence.unsupported_claim_count
    assert "evidence_status" in bundle.repository_manifest.hosted_manifest_json_fields


def test_missing_visual_evidence_does_not_falsely_approve_publishability(monkeypatch) -> None:
    monkeypatch.setenv(ENV_VISUAL_EVIDENCE_FLAG, "yes")
    raw = _tiny_job().model_dump()
    raw["visual_frames"] = []
    job = FeedFoundryJobInput.model_validate(raw)
    bundle = run_feedfoundry_agent_bundle(job)

    assert bundle.visual_evidence.visual_evidence_available is False
    assert bundle.visual_evidence.evidence_status == "needs_review"
    assert bundle.hosted_manifest_hints.evidence_status == "needs_review"
    assert bundle.geo_freshness.human_review_required is True
    assert "missing_visual_evidence" in " ".join(bundle.visual_evidence.evidence_gate_reason)


def test_transcript_and_visual_evidence_passing_gives_ready_status(monkeypatch) -> None:
    monkeypatch.setenv(ENV_VISUAL_EVIDENCE_FLAG, "1")
    bundle = run_feedfoundry_agent_bundle(_passing_job())

    assert bundle.visual_evidence.evidence_status == "ready"
    assert bundle.visual_evidence.visual_evidence_available is True
    assert bundle.visual_evidence.transcript_evidence_available is True
    assert bundle.visual_evidence.unsupported_claim_count == 0
    assert bundle.visual_evidence.human_review_required is False
    assert bundle.visual_evidence.final_evidence_confidence >= 0.75
    assert bundle.hosted_manifest_hints.evidence_status == "ready"
    assert bundle.geo_freshness.evidence_status == "ready"
    assert bundle.repository_manifest.evidence_status == "ready"


def test_visual_evidence_integration_does_not_change_processing_minute_settlement() -> None:
    import worker as worker_mod

    src = inspect.getsource(worker_mod.process_job)
    assert src.index("_write_stub_outputs") < src.index("_settle_processing_allowance")


def test_visual_evidence_integration_introduces_no_provider_call_tokens() -> None:
    paths = [
        WORKER_ROOT / "ai" / "feedfoundry_agents" / "orchestrator.py",
        WORKER_ROOT / "ai" / "feedfoundry_agents" / "schemas.py",
        WORKER_ROOT / "ai" / "feedfoundry_agents" / "integration.py",
        WORKER_ROOT / "ai" / "feedfoundry_agents" / "visual_evidence" / "orchestrator.py",
        WORKER_ROOT / "ai" / "feedfoundry_agents" / "visual_evidence" / "schemas.py",
        WORKER_ROOT / "worker.py",
    ]
    forbidden = ["openai(", "openrouter", "httpx.", "requests.", "anthropic", "provider_client"]
    haystack = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)

    assert [token for token in forbidden if token in haystack] == []
