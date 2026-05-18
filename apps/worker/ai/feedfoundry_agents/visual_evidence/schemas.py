"""Pydantic schemas for the deterministic FeedFoundry visual/evidence squad."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


EntityType = Literal["product", "object", "logo", "person"]
ClaimSource = Literal["transcript", "visual", "generated"]
SupportStatus = Literal["supported", "unsupported", "needs_review"]
EvidenceGate = Literal["approve", "hold", "review"]


class VisualEntityInput(StrictModel):
    entity_type: EntityType
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_notes: list[str] = Field(default_factory=list)


class KeyframeInput(StrictModel):
    keyframe_id: str
    timestamp_seconds: float = Field(ge=0.0)
    frame_uri: str
    visual_label: str = ""
    ocr_text: str = ""
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: list[VisualEntityInput] = Field(default_factory=list)


class TranscriptChunkInput(StrictModel):
    chunk_id: str
    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(ge=0.0)
    text: str = ""


class ClaimInput(StrictModel):
    claim_text: str
    source: ClaimSource = "generated"


class HostedManifestCandidateInput(StrictModel):
    publishability_gate: str = "hold"
    title: str = ""


class VisualEvidenceInput(StrictModel):
    media_id: str
    keyframes: list[KeyframeInput] = Field(default_factory=list)
    transcript_chunks: list[TranscriptChunkInput] = Field(default_factory=list)
    claims: list[ClaimInput] = Field(default_factory=list)
    hosted_manifest_candidate: HostedManifestCandidateInput = Field(default_factory=HostedManifestCandidateInput)


class EvidencePointer(StrictModel):
    keyframe_id: str
    timestamp_seconds: float
    artifact_uri: str


class VisualIntelligencePlaceholder(StrictModel):
    media_id: str
    keyframe_id: str
    timestamp_seconds: float
    frame_uri: str
    visual_summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)


class OcrTextPlaceholder(StrictModel):
    detected_text: str
    bounding_region_placeholder: dict[str, Any]
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_pointer: EvidencePointer


class EntityPresencePlaceholder(StrictModel):
    entity_type: EntityType
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_pointer: EvidencePointer
    risk_notes: list[str] = Field(default_factory=list)


class VisualEvidencePointer(StrictModel):
    keyframe_reference: str
    timestamp_seconds: float
    artifact_uri: str
    visual_observation: str
    confidence: float = Field(ge=0.0, le=1.0)


class TranscriptEvidencePointer(StrictModel):
    transcript_chunk_id: str
    timestamp_range: dict[str, float]
    quote_text_excerpt: str
    claim_text: str
    claim_supported: bool
    confidence: float = Field(ge=0.0, le=1.0)


class UnsupportedClaimReportItem(StrictModel):
    claim_text: str
    source: ClaimSource
    support_status: SupportStatus
    missing_evidence_reason: str
    escalation_flag: bool


class ConfidenceScores(StrictModel):
    media_confidence: float = Field(ge=0.0, le=1.0)
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    visual_confidence: float = Field(ge=0.0, le=1.0)
    transcript_confidence: float = Field(ge=0.0, le=1.0)
    final_evidence_confidence: float = Field(ge=0.0, le=1.0)


class EscalationFlags(StrictModel):
    missing_transcript_evidence: bool
    missing_visual_evidence: bool
    low_ocr_confidence: bool
    possible_hallucination: bool
    human_review_required: bool


class EvidenceGateOutput(StrictModel):
    input_hosted_manifest_gate: str
    hosted_manifest_publishability_gate: EvidenceGate
    gate: EvidenceGate
    approval_without_evidence_blocked: bool
    reasons: list[str] = Field(default_factory=list)


class VisualEvidenceSquadOutput(StrictModel):
    schema_version: Literal["0.1"] = "0.1"
    agent_id: Literal["visual_evidence_squad"] = "visual_evidence_squad"
    execution_mode: Literal["deterministic_mock"] = "deterministic_mock"
    media_id: str
    visual_intelligence: list[VisualIntelligencePlaceholder]
    ocr_text: list[OcrTextPlaceholder]
    entities: list[EntityPresencePlaceholder]
    visual_evidence: list[VisualEvidencePointer]
    transcript_evidence: list[TranscriptEvidencePointer]
    unsupported_claim_report: list[UnsupportedClaimReportItem]
    confidence_scores: ConfidenceScores
    escalation_flags: EscalationFlags
    evidence_gate: EvidenceGateOutput
