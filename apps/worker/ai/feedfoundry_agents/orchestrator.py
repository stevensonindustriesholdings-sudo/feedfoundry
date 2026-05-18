"""Deterministic orchestration for the FeedFoundry v0.1 agent bundle."""

from __future__ import annotations

import os

from ai.feedfoundry_agents.agents.captain import run_captain
from ai.feedfoundry_agents.agents.chapter_architect import run_chapter_architect
from ai.feedfoundry_agents.agents.clean_transcript import run_clean_transcript
from ai.feedfoundry_agents.agents.clip_scout import run_clip_scout
from ai.feedfoundry_agents.agents.cta_designer import run_cta_designer
from ai.feedfoundry_agents.agents.export_bundle import run_export_bundle_assembler
from ai.feedfoundry_agents.agents.fact_sheet import run_fact_sheet
from ai.feedfoundry_agents.agents.faq_author import run_faq_author
from ai.feedfoundry_agents.agents.ffmpeg_failure import classify_ffmpeg_failure
from ai.feedfoundry_agents.agents.geo_freshness import run_geo_freshness
from ai.feedfoundry_agents.agents.hosted_manifest import run_hosted_manifest_composer
from ai.feedfoundry_agents.agents.judge import run_judge
from ai.feedfoundry_agents.agents.metadata_curator import run_metadata_curator
from ai.feedfoundry_agents.agents.repository_manifest import run_repository_manifest_librarian
from ai.feedfoundry_agents.agents.schema_org import run_schema_org_specialist
from ai.feedfoundry_agents.agents.show_notes import run_show_notes_writer
from ai.feedfoundry_agents.agents.transcript_steward import run_transcript_steward
from ai.feedfoundry_agents.agents.verifier import run_verifier
from ai.feedfoundry_agents.schemas import (
    BundleRunMeta,
    EvidenceIntegrationStatus,
    FeedFoundryAgentBundleOutput,
    FeedFoundryAgentBundleWithVisualEvidenceOutput,
    FeedFoundryJobInput,
    GeoFreshnessEvidenceOutput,
    HostedManifestEvidenceHintsOutput,
    JudgeOutput,
    JudgeVerdict,
    RepositoryManifestEvidenceOutput,
    VerifierOutput,
)
from ai.feedfoundry_agents.visual_evidence.orchestrator import run_visual_evidence_squad

ENV_VISUAL_EVIDENCE_FLAG = "FF_WORKER_VISUAL_EVIDENCE_ENABLED"


def visual_evidence_enabled() -> bool:
    return os.environ.get(ENV_VISUAL_EVIDENCE_FLAG, "").lower().strip() in {"1", "true", "yes"}


def _build_visual_evidence_input(job_input: FeedFoundryJobInput, hosted_manifest_hints) -> dict:
    keyframes = []
    for idx, frame in enumerate(job_input.visual_frames, start=1):
        label = (frame.label or "").strip()
        keyframes.append(
            {
                "keyframe_id": f"kf_{idx:04d}",
                "timestamp_seconds": float(frame.t_seconds),
                "frame_uri": frame.frame_uri or f"artifacts/{job_input.media_asset_id}/keyframes/kf_{idx:04d}.jpg",
                "visual_label": label or "visual evidence unavailable placeholder",
                "ocr_text": label,
                "ocr_confidence": 0.72 if label else 0.0,
                "entities": [
                    {
                        "entity_type": "object",
                        "label": label or "visual placeholder",
                        "confidence": 0.72 if label else 0.0,
                        "risk_notes": [] if label else ["visual_frame_missing_label_or_keyframe_artifact"],
                    }
                ] if label else [],
            }
        )
    transcript_chunks = [
        {
            "chunk_id": f"tc_{idx:04d}",
            "start_seconds": float(seg.start),
            "end_seconds": float(seg.end),
            "text": seg.text,
        }
        for idx, seg in enumerate(job_input.transcript.segments, start=1)
    ]
    claims = []
    first_transcript = next((seg.text.strip() for seg in job_input.transcript.segments if seg.text.strip()), "")
    if first_transcript:
        claims.append({"claim_text": first_transcript[:180], "source": "transcript"})
    first_visual = next(((frame.label or "").strip() for frame in job_input.visual_frames if (frame.label or "").strip()), "")
    if first_visual:
        claims.append({"claim_text": first_visual[:180], "source": "visual"})
    if not first_visual or first_visual.lower() in {"opening", "t0", "visual evidence unavailable placeholder"} or first_visual.lower().startswith("chunk_"):
        claims.append({"claim_text": "The media includes a verified product demonstration.", "source": "generated"})
    return {
        "media_id": job_input.media_asset_id,
        "keyframes": keyframes,
        "transcript_chunks": transcript_chunks,
        "claims": claims,
        "hosted_manifest_candidate": {
            "publishability_gate": "approve",
            "title": hosted_manifest_hints.canonical_title,
        },
    }


def _summarise_visual_evidence(
    package: dict,
    *,
    visual_evidence_package_uri: str | None = None,
    artifact_write_failed: bool = False,
) -> EvidenceIntegrationStatus:
    unsupported = sum(1 for item in package.get("unsupported_claim_report", []) if item.get("support_status") == "unsupported")
    visual_available = bool(package.get("visual_evidence")) and not package.get("escalation_flags", {}).get("missing_visual_evidence", False)
    transcript_available = bool(package.get("transcript_evidence"))
    human_review = bool(package.get("escalation_flags", {}).get("human_review_required", True))
    final_confidence = float(package.get("confidence_scores", {}).get("final_evidence_confidence", 0.0) or 0.0)
    if unsupported:
        final_confidence = min(final_confidence, 0.74)
    gate_reasons = list(package.get("evidence_gate", {}).get("reasons", []))
    if artifact_write_failed:
        status = "artifact_write_failed"
        human_review = True
        final_confidence = min(final_confidence, 0.74)
        gate_reasons.append("visual_evidence_artifact_write_failed")
    elif visual_available and transcript_available and unsupported == 0 and not human_review and final_confidence >= 0.75:
        status = "ready"
    else:
        status = "needs_review"
    return EvidenceIntegrationStatus(
        evidence_status=status,
        visual_evidence_available=visual_available,
        transcript_evidence_available=transcript_available,
        unsupported_claim_count=unsupported,
        human_review_required=human_review,
        final_evidence_confidence=round(final_confidence, 3),
        visual_evidence_package_uri=visual_evidence_package_uri,
        visual_evidence_package_object=package,
        evidence_gate_reason=gate_reasons,
    )


def _hosted_with_evidence(hosted_manifest_hints, summary: EvidenceIntegrationStatus) -> HostedManifestEvidenceHintsOutput:
    data = hosted_manifest_hints.model_dump()
    outputs = list(data.get("outputs_available") or [])
    if summary.visual_evidence_package_uri and "visual_evidence.json" not in outputs:
        outputs.append("visual_evidence.json")
    data["outputs_available"] = outputs
    data.update(summary.model_dump(exclude={"visual_evidence_package_object"}))
    return HostedManifestEvidenceHintsOutput.model_validate(data)


def _repository_with_evidence(repository_manifest, summary: EvidenceIntegrationStatus) -> RepositoryManifestEvidenceOutput:
    data = repository_manifest.model_dump()
    fields = list(data.get("hosted_manifest_json_fields") or [])
    for field in [
        "evidence_status",
        "visual_evidence_available",
        "transcript_evidence_available",
        "unsupported_claim_count",
        "human_review_required",
        "final_evidence_confidence",
        "visual_evidence_package_uri",
        "evidence_gate_reason",
    ]:
        if field not in fields:
            fields.append(field)
    data["hosted_manifest_json_fields"] = fields
    data["llms_full_txt_candidate"] = data["llms_full_txt_candidate"] + (
        f"- Evidence status: {summary.evidence_status}; "
        f"human_review_required={str(summary.human_review_required).lower()}.\n"
    )
    data.update(summary.model_dump(exclude={"visual_evidence_package_object"}))
    return RepositoryManifestEvidenceOutput.model_validate(data)


def _geo_with_evidence(geo_freshness, summary: EvidenceIntegrationStatus) -> GeoFreshnessEvidenceOutput:
    data = geo_freshness.model_dump()
    data["freshness_notes"] = list(data.get("freshness_notes") or []) + [
        f"Evidence status: {summary.evidence_status}; hosted/GEO publishability requires ready evidence or explicit unavailable handling."
    ]
    data.update(summary.model_dump(exclude={"visual_evidence_package_object"}))
    return GeoFreshnessEvidenceOutput.model_validate(data)


def _bundle_with_visual_evidence(
    bundle: FeedFoundryAgentBundleOutput,
    job_input: FeedFoundryJobInput,
    *,
    visual_evidence_package_uri: str | None = None,
    artifact_write_failed: bool = False,
) -> FeedFoundryAgentBundleWithVisualEvidenceOutput:
    package = run_visual_evidence_squad(_build_visual_evidence_input(job_input, bundle.hosted_manifest_hints))
    summary = _summarise_visual_evidence(
        package,
        visual_evidence_package_uri=visual_evidence_package_uri,
        artifact_write_failed=artifact_write_failed,
    )
    return FeedFoundryAgentBundleWithVisualEvidenceOutput.model_validate(
        {
            **bundle.model_dump(),
            "run": bundle.run.model_copy(update={"agents_scheduled": [*bundle.run.agents_scheduled, "visual_evidence_squad"]}).model_dump(),
            "hosted_manifest_hints": _hosted_with_evidence(bundle.hosted_manifest_hints, summary).model_dump(),
            "repository_manifest": _repository_with_evidence(bundle.repository_manifest, summary).model_dump(),
            "geo_freshness": _geo_with_evidence(bundle.geo_freshness, summary).model_dump(),
            "visual_evidence": summary.model_dump(),
        }
    )


def run_feedfoundry_agent_bundle(
    job_input: FeedFoundryJobInput,
    *,
    visual_evidence_package_uri: str | None = None,
    visual_evidence_artifact_write_failed: bool = False,
) -> FeedFoundryAgentBundleOutput | FeedFoundryAgentBundleWithVisualEvidenceOutput:
    """Execute the full agent bundle in fixed order (deterministic, no network I/O)."""
    scheduled = [
        "captain",
        "transcript_steward",
        "clean_transcript_editor",
        "chapter_architect",
        "clip_scout",
        "show_notes_writer",
        "metadata_curator",
        "cta_designer",
        "fact_sheet_analyst",
        "faq_author",
        "hosted_manifest_composer",
        "export_bundle_assembler",
        "repository_manifest_librarian",
        "schema_org_specialist",
        "geo_freshness",
        "verifier",
        "judge",
    ]
    if job_input.ffmpeg_failure is not None:
        scheduled.insert(-2, "ffmpeg_failure_classifier")

    captain = run_captain(job_input)
    transcript_steward = run_transcript_steward(job_input)
    clean_transcript = run_clean_transcript(job_input)
    chapters = run_chapter_architect(job_input)
    clip_candidates = run_clip_scout(job_input)
    show_notes = run_show_notes_writer(job_input)
    metadata = run_metadata_curator(job_input)
    ctas = run_cta_designer(job_input)
    fact_sheet = run_fact_sheet(job_input)
    faqs = run_faq_author(job_input)
    hosted_manifest_hints = run_hosted_manifest_composer(job_input)
    export_bundle_hints = run_export_bundle_assembler(job_input)
    repository_manifest = run_repository_manifest_librarian(job_input)
    schema_org = run_schema_org_specialist(job_input)
    geo_freshness = run_geo_freshness(job_input)
    ffmpeg_failure = classify_ffmpeg_failure(job_input.ffmpeg_failure) if job_input.ffmpeg_failure else None

    placeholder_verification = VerifierOutput(passed=True, issues=[])
    placeholder_judge = JudgeOutput(verdict=JudgeVerdict.PASS, rationale="pending")

    bundle = FeedFoundryAgentBundleOutput(
        run=BundleRunMeta(agents_scheduled=scheduled),
        captain=captain,
        transcript_steward=transcript_steward,
        clean_transcript=clean_transcript,
        chapters=chapters,
        clip_candidates=clip_candidates,
        show_notes=show_notes,
        metadata=metadata,
        ctas=ctas,
        fact_sheet=fact_sheet,
        faqs=faqs,
        hosted_manifest_hints=hosted_manifest_hints,
        export_bundle_hints=export_bundle_hints,
        repository_manifest=repository_manifest,
        schema_org=schema_org,
        verification=placeholder_verification,
        judge=placeholder_judge,
        geo_freshness=geo_freshness,
        ffmpeg_failure=ffmpeg_failure,
    )

    verification = run_verifier(job_input, bundle)
    judge = run_judge(verification)
    verified_bundle = bundle.model_copy(update={"verification": verification, "judge": judge})
    if visual_evidence_enabled():
        return _bundle_with_visual_evidence(
            verified_bundle,
            job_input,
            visual_evidence_package_uri=visual_evidence_package_uri,
            artifact_write_failed=visual_evidence_artifact_write_failed,
        )
    return verified_bundle
