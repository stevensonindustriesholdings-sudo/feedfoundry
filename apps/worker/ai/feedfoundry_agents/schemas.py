"""Strict Pydantic models for the FeedFoundry Hermes-style agent bundle (v0.1)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# --- Job input -----------------------------------------------------------------


class TranscriptSegmentIn(StrictModel):
    start: float = 0.0
    end: float = 0.0
    text: str = ""


class TranscriptPayloadIn(StrictModel):
    schema_version: str = "1.0"
    segments: list[TranscriptSegmentIn] = Field(default_factory=list)


class VisualFrameIn(StrictModel):
    t_seconds: float = 0.0
    label: str | None = None
    frame_uri: str | None = None


class ProductContextIn(StrictModel):
    show_name: str = ""
    niche: str = ""
    primary_topics: list[str] = Field(default_factory=list)


class MediaMetaIn(StrictModel):
    duration_seconds: float | None = None
    container_format: str | None = None


class FFmpegFailureInput(StrictModel):
    """Optional probe payload for the FFmpeg failure classifier (standalone)."""

    return_code: int = -1
    stderr_snippet: str = ""
    command_summary: str = ""
    stage: str = "audio_extract"


class FeedFoundryJobInput(StrictModel):
    job_id: str
    organisation_id: str
    media_asset_id: str
    creator_slug: str = "demo-creator"
    asset_slug: str = "episode-001"
    original_basename: str | None = "sample.mp4"
    transcript: TranscriptPayloadIn
    visual_frames: list[VisualFrameIn] = Field(default_factory=list)
    product_context: ProductContextIn = Field(default_factory=ProductContextIn)
    media_meta: MediaMetaIn = Field(default_factory=MediaMetaIn)
    ffmpeg_failure: FFmpegFailureInput | None = None


# --- Captain / run meta --------------------------------------------------------


class BundleRunMeta(StrictModel):
    schema_version: str = "0.1"
    execution_mode: Literal["deterministic_mock"] = "deterministic_mock"
    agents_scheduled: list[str] = Field(default_factory=list)


class CaptainOutput(StrictModel):
    agent_id: Literal["captain"] = "captain"
    schema_version: str = "0.1"
    normalised_title: str
    summary_seed: str
    notes: list[str] = Field(default_factory=list)


# --- Core creative agents (structured hints, not customer JSON verbatim) ------


class TranscriptStewardOutput(StrictModel):
    agent_id: Literal["transcript_steward"] = "transcript_steward"
    schema_version: str = "0.1"
    segment_count: int
    derived_from: str = "input.transcript"
    anomalies: list[str] = Field(default_factory=list)


class CleanTranscriptOutput(StrictModel):
    agent_id: Literal["clean_transcript_editor"] = "clean_transcript_editor"
    schema_version: str = "0.1"
    paragraphs: list[str]
    derived_from: str = "input.transcript"


class ChapterOut(StrictModel):
    title: str
    start_seconds: float
    summary: str = ""


class ChapterArchitectOutput(StrictModel):
    agent_id: Literal["chapter_architect"] = "chapter_architect"
    schema_version: str = "0.1"
    chapters: list[ChapterOut]
    derived_from: str = "input.transcript"


class ClipCandidateOut(StrictModel):
    start_seconds: float
    end_seconds: float
    hook: str
    rationale: str


class ClipScoutOutput(StrictModel):
    agent_id: Literal["clip_scout"] = "clip_scout"
    schema_version: str = "0.1"
    clips: list[ClipCandidateOut]
    derived_from: str = "input.transcript"


class ShowNotesOutput(StrictModel):
    agent_id: Literal["show_notes_writer"] = "show_notes_writer"
    schema_version: str = "0.1"
    title: str
    bullets: list[str]
    resources: list[str] = Field(default_factory=list)
    derived_from: str = "input.transcript"


class MetadataCuratorOutput(StrictModel):
    agent_id: Literal["metadata_curator"] = "metadata_curator"
    schema_version: str = "0.1"
    youtube: dict[str, Any] = Field(default_factory=dict)
    podcast: dict[str, Any] = Field(default_factory=dict)
    derived_from: str = "input.transcript+product_context"


class CtaOut(StrictModel):
    label: str
    intent: str
    url: str | None = None


class CtaDesignerOutput(StrictModel):
    agent_id: Literal["cta_designer"] = "cta_designer"
    schema_version: str = "0.1"
    ctas: list[CtaOut]
    derived_from: str = "input.transcript"


class FactLineOut(StrictModel):
    statement: str
    source_span: str | None = None


class FactSheetOutput(StrictModel):
    agent_id: Literal["fact_sheet_analyst"] = "fact_sheet_analyst"
    schema_version: str = "0.1"
    facts: list[FactLineOut]
    derived_from: str = "input.transcript"


class FaqOut(StrictModel):
    question: str
    answer: str


class FaqAuthorOutput(StrictModel):
    agent_id: Literal["faq_author"] = "faq_author"
    schema_version: str = "0.1"
    faqs: list[FaqOut]
    derived_from: str = "input.transcript"


class HostedManifestHintsOutput(StrictModel):
    """Curates fields aligned with ``build_hosted_manifest_from_transcript`` public shape."""

    agent_id: Literal["hosted_manifest_composer"] = "hosted_manifest_composer"
    schema_version: str = "0.1"
    canonical_title: str
    summary: str
    outputs_available: list[str]
    seo_meta_title: str
    seo_meta_description: str
    keywords: list[str]
    derived_from: str = "input.transcript+media_meta"


class ExportBundleHintsOutput(StrictModel):
    agent_id: Literal["export_bundle_assembler"] = "export_bundle_assembler"
    schema_version: str = "0.1"
    artefact_filenames: list[str]
    index_notes: list[str] = Field(default_factory=list)


class RepositoryManifestOutput(StrictModel):
    agent_id: Literal["repository_manifest_librarian"] = "repository_manifest_librarian"
    schema_version: str = "0.1"
    llms_txt_candidate: str
    llms_full_txt_candidate: str
    hosted_manifest_json_fields: list[str] = Field(
        default_factory=lambda: [
            "schema_version",
            "creator_slug",
            "asset_slug",
            "canonical_title",
            "summary",
            "duration_seconds",
            "chapters",
            "topics",
            "facts",
            "faqs",
            "ctas",
            "outputs_available",
            "derived_from",
        ]
    )


class SchemaOrgOutput(StrictModel):
    agent_id: Literal["schema_org_specialist"] = "schema_org_specialist"
    schema_version: str = "0.1"
    json_ld: dict[str, Any]


class VerifierIssue(StrictModel):
    code: str
    message: str
    agent_id: str | None = None


class VerifierOutput(StrictModel):
    agent_id: Literal["verifier"] = "verifier"
    schema_version: str = "0.1"
    passed: bool
    issues: list[VerifierIssue] = Field(default_factory=list)


class JudgeVerdict(str, Enum):
    PASS = "pass"
    PASS_WITH_NOTES = "pass_with_notes"
    BLOCKED = "blocked"


class JudgeOutput(StrictModel):
    agent_id: Literal["judge"] = "judge"
    schema_version: str = "0.1"
    verdict: JudgeVerdict
    rationale: str


class GeoCitation(StrictModel):
    label: str
    source: Literal["fixture_seed"] = "fixture_seed"


class GeoFreshnessOutput(StrictModel):
    agent_id: Literal["geo_freshness"] = "geo_freshness"
    schema_version: str = "0.1"
    mode: Literal["static_fixture", "live_requested_stubbed"] = "static_fixture"
    reviewed_at: str
    freshness_notes: list[str]
    citations: list[GeoCitation] = Field(default_factory=list)
    live_research_requested: bool = False


class EvidenceIntegrationStatus(StrictModel):
    evidence_status: Literal["ready", "needs_review", "unavailable"]
    visual_evidence_available: bool
    transcript_evidence_available: bool
    unsupported_claim_count: int = Field(ge=0)
    human_review_required: bool
    final_evidence_confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence_package_uri: str | None = None
    visual_evidence_package_object: dict[str, Any] | None = None
    evidence_gate_reason: list[str] = Field(default_factory=list)


class HostedManifestEvidenceHintsOutput(HostedManifestHintsOutput):
    evidence_status: Literal["ready", "needs_review", "unavailable"]
    visual_evidence_available: bool
    transcript_evidence_available: bool
    unsupported_claim_count: int = Field(ge=0)
    human_review_required: bool
    final_evidence_confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence_package_uri: str | None = None
    evidence_gate_reason: list[str] = Field(default_factory=list)


class RepositoryManifestEvidenceOutput(RepositoryManifestOutput):
    evidence_status: Literal["ready", "needs_review", "unavailable"]
    visual_evidence_available: bool
    transcript_evidence_available: bool
    unsupported_claim_count: int = Field(ge=0)
    human_review_required: bool
    final_evidence_confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence_package_uri: str | None = None
    evidence_gate_reason: list[str] = Field(default_factory=list)


class GeoFreshnessEvidenceOutput(GeoFreshnessOutput):
    evidence_status: Literal["ready", "needs_review", "unavailable"]
    visual_evidence_available: bool
    transcript_evidence_available: bool
    unsupported_claim_count: int = Field(ge=0)
    human_review_required: bool
    final_evidence_confidence: float = Field(ge=0.0, le=1.0)
    visual_evidence_package_uri: str | None = None
    evidence_gate_reason: list[str] = Field(default_factory=list)


class FFmpegFailureClassification(StrictModel):
    agent_id: Literal["ffmpeg_failure_classifier"] = "ffmpeg_failure_classifier"
    schema_version: str = "0.1"
    failure_family: str
    confidence_0_1: float = Field(ge=0.0, le=1.0)
    debit_processing_minutes: Literal[False] = False
    remediation_hint: str = ""


class FeedFoundryAgentBundleOutput(StrictModel):
    run: BundleRunMeta
    captain: CaptainOutput
    transcript_steward: TranscriptStewardOutput
    clean_transcript: CleanTranscriptOutput
    chapters: ChapterArchitectOutput
    clip_candidates: ClipScoutOutput
    show_notes: ShowNotesOutput
    metadata: MetadataCuratorOutput
    ctas: CtaDesignerOutput
    fact_sheet: FactSheetOutput
    faqs: FaqAuthorOutput
    hosted_manifest_hints: HostedManifestHintsOutput
    export_bundle_hints: ExportBundleHintsOutput
    repository_manifest: RepositoryManifestOutput
    schema_org: SchemaOrgOutput
    verification: VerifierOutput
    judge: JudgeOutput
    geo_freshness: GeoFreshnessOutput
    ffmpeg_failure: FFmpegFailureClassification | None = None


class FeedFoundryAgentBundleWithVisualEvidenceOutput(StrictModel):
    run: BundleRunMeta
    captain: CaptainOutput
    transcript_steward: TranscriptStewardOutput
    clean_transcript: CleanTranscriptOutput
    chapters: ChapterArchitectOutput
    clip_candidates: ClipScoutOutput
    show_notes: ShowNotesOutput
    metadata: MetadataCuratorOutput
    ctas: CtaDesignerOutput
    fact_sheet: FactSheetOutput
    faqs: FaqAuthorOutput
    hosted_manifest_hints: HostedManifestEvidenceHintsOutput
    export_bundle_hints: ExportBundleHintsOutput
    repository_manifest: RepositoryManifestEvidenceOutput
    schema_org: SchemaOrgOutput
    verification: VerifierOutput
    judge: JudgeOutput
    geo_freshness: GeoFreshnessEvidenceOutput
    ffmpeg_failure: FFmpegFailureClassification | None = None
    visual_evidence: EvidenceIntegrationStatus
