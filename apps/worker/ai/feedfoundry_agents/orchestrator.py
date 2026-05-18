"""Deterministic orchestration for the FeedFoundry v0.1 agent bundle."""

from __future__ import annotations

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
    FeedFoundryAgentBundleOutput,
    FeedFoundryJobInput,
    JudgeOutput,
    JudgeVerdict,
    VerifierOutput,
)


def run_feedfoundry_agent_bundle(job_input: FeedFoundryJobInput) -> FeedFoundryAgentBundleOutput:
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
    return bundle.model_copy(update={"verification": verification, "judge": judge})
