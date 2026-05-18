"""Deterministic visual/evidence squad orchestration for FeedFoundry.

This module is offline/local-first: no OCR vendor, no object detector, no live AI
provider, no storage mutation, and no processing-minute ledger changes.
It creates a strict evidence package that later real keyframe/OCR/object detectors
can replace behind provider/env gates.
"""

from __future__ import annotations

import re
from statistics import mean
from typing import Iterable

from ai.feedfoundry_agents.visual_evidence.schemas import (
    ConfidenceScores,
    EntityPresencePlaceholder,
    EscalationFlags,
    EvidenceGateOutput,
    EvidencePointer,
    OcrTextPlaceholder,
    TranscriptEvidencePointer,
    UnsupportedClaimReportItem,
    VisualEvidenceInput,
    VisualEvidencePointer,
    VisualEvidenceSquadOutput,
    VisualIntelligencePlaceholder,
)

LOW_OCR_THRESHOLD = 0.6
FINAL_APPROVAL_THRESHOLD = 0.75


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) > 2 and t not in {"the", "and", "for", "with", "this", "that", "here", "video"}
    }


def _overlap_score(claim: str, text: str) -> float:
    ct = _tokens(claim)
    tt = _tokens(text)
    if not ct or not tt:
        return 0.0
    return len(ct & tt) / len(ct)


def _avg(values: Iterable[float], default: float = 0.0) -> float:
    vals = [max(0.0, min(1.0, float(v))) for v in values]
    return round(mean(vals), 3) if vals else default


def _frame_confidence(label: str, ocr_confidence: float, entity_confidences: list[float]) -> float:
    label_bonus = 0.12 if label.strip() else 0.0
    entity_score = _avg(entity_confidences, default=0.45)
    score = 0.28 + label_bonus + (0.3 * max(0.0, min(1.0, ocr_confidence))) + (0.3 * entity_score)
    return round(max(0.05, min(0.95, score)), 3)


def _pointer(frame) -> EvidencePointer:
    return EvidencePointer(
        keyframe_id=frame.keyframe_id,
        timestamp_seconds=frame.timestamp_seconds,
        artifact_uri=frame.frame_uri,
    )


def _build_visual_intelligence(inp: VisualEvidenceInput) -> list[VisualIntelligencePlaceholder]:
    out: list[VisualIntelligencePlaceholder] = []
    for frame in inp.keyframes:
        entity_conf = [e.confidence for e in frame.entities]
        summary = frame.visual_label.strip() or "Deterministic placeholder keyframe observation; real visual model not invoked."
        out.append(
            VisualIntelligencePlaceholder(
                media_id=inp.media_id,
                keyframe_id=frame.keyframe_id,
                timestamp_seconds=frame.timestamp_seconds,
                frame_uri=frame.frame_uri,
                visual_summary=summary,
                confidence_score=_frame_confidence(summary, frame.ocr_confidence, entity_conf),
            )
        )
    return out


def _build_ocr(inp: VisualEvidenceInput) -> list[OcrTextPlaceholder]:
    out: list[OcrTextPlaceholder] = []
    for frame in inp.keyframes:
        out.append(
            OcrTextPlaceholder(
                detected_text=frame.ocr_text,
                bounding_region_placeholder={
                    "shape": "full_frame_placeholder",
                    "x": 0.0,
                    "y": 0.0,
                    "width": 1.0,
                    "height": 1.0,
                    "source": "deterministic_fixture_or_stub",
                },
                confidence_score=round(frame.ocr_confidence, 3),
                evidence_pointer=_pointer(frame),
            )
        )
    return out


def _build_entities(inp: VisualEvidenceInput) -> list[EntityPresencePlaceholder]:
    out: list[EntityPresencePlaceholder] = []
    for frame in inp.keyframes:
        for entity in frame.entities:
            notes = list(entity.risk_notes)
            if entity.confidence < 0.5:
                notes.append("low_confidence_placeholder_requires_human_review")
            out.append(
                EntityPresencePlaceholder(
                    entity_type=entity.entity_type,
                    label=entity.label,
                    confidence=round(entity.confidence, 3),
                    evidence_pointer=_pointer(frame),
                    risk_notes=notes,
                )
            )
    return out


def _build_visual_evidence(visual: list[VisualIntelligencePlaceholder]) -> list[VisualEvidencePointer]:
    return [
        VisualEvidencePointer(
            keyframe_reference=item.keyframe_id,
            timestamp_seconds=item.timestamp_seconds,
            artifact_uri=item.frame_uri,
            visual_observation=item.visual_summary,
            confidence=item.confidence_score,
        )
        for item in visual
    ]


def _best_transcript_support(inp: VisualEvidenceInput, claim_text: str) -> tuple[object | None, float]:
    best = None
    best_score = 0.0
    for chunk in inp.transcript_chunks:
        score = _overlap_score(claim_text, chunk.text)
        if score > best_score:
            best = chunk
            best_score = score
    return best, round(min(0.95, best_score), 3)


def _best_visual_support(inp: VisualEvidenceInput, claim_text: str) -> tuple[object | None, float]:
    best = None
    best_score = 0.0
    for frame in inp.keyframes:
        blob = " ".join([frame.visual_label, frame.ocr_text, " ".join(e.label for e in frame.entities)])
        score = _overlap_score(claim_text, blob)
        if score > best_score:
            best = frame
            best_score = score
    return best, round(min(0.95, best_score), 3)


def _build_transcript_evidence(inp: VisualEvidenceInput) -> list[TranscriptEvidencePointer]:
    out: list[TranscriptEvidencePointer] = []
    for claim in inp.claims:
        chunk, score = _best_transcript_support(inp, claim.claim_text)
        supported = bool(chunk is not None and score >= 0.45)
        if chunk is not None:
            out.append(
                TranscriptEvidencePointer(
                    transcript_chunk_id=chunk.chunk_id,
                    timestamp_range={"start_seconds": chunk.start_seconds, "end_seconds": chunk.end_seconds},
                    quote_text_excerpt=chunk.text[:240],
                    claim_text=claim.claim_text,
                    claim_supported=supported,
                    confidence=score if supported else min(score, 0.4),
                )
            )
    return out


def _claim_requires_exact_numeric_support(claim_text: str) -> bool:
    return bool(re.search(r"(?:\$|\b\d+(?:\.\d+)?\s*(?:m|million|k|thousand|%|percent)\b)", claim_text.lower()))


def _claim_numeric_markers(claim_text: str) -> list[str]:
    return [m.group(0).lower().replace("$", "").strip() for m in re.finditer(r"\$?\d+(?:\.\d+)?\s*(?:m|million|k|thousand|%|percent)?", claim_text.lower())]


def _build_claim_report(inp: VisualEvidenceInput, transcript_evidence: list[TranscriptEvidencePointer]) -> list[UnsupportedClaimReportItem]:
    by_claim = {e.claim_text: e for e in transcript_evidence}
    report: list[UnsupportedClaimReportItem] = []
    for claim in inp.claims:
        transcript = by_claim.get(claim.claim_text)
        visual_frame, visual_score = _best_visual_support(inp, claim.claim_text)
        transcript_supported = bool(transcript and transcript.claim_supported)
        visual_supported = bool(visual_frame is not None and visual_score >= 0.45)
        numeric_markers = _claim_numeric_markers(claim.claim_text)
        evidence_blob = "\n".join([chunk.text.lower().replace("$", "") for chunk in inp.transcript_chunks])
        exact_numeric_missing = _claim_requires_exact_numeric_support(claim.claim_text) and not any(
            marker and marker in evidence_blob for marker in numeric_markers
        )
        if exact_numeric_missing:
            status = "unsupported"
            reason = "Numeric or money claim requires exact supporting transcript/visual evidence; only vague adjacent language was found."
            escalate = True
        elif transcript_supported or visual_supported:
            status = "supported"
            reason = "Supported by transcript evidence." if transcript_supported else "Supported by visual keyframe evidence."
            escalate = False
        elif visual_score > 0.28 or (transcript and transcript.confidence > 0.28):
            status = "needs_review"
            reason = "Partial lexical overlap exists but deterministic evidence confidence is below support threshold."
            escalate = True
        else:
            status = "unsupported"
            reason = "No transcript chunk or keyframe placeholder provides enough evidence for this claim."
            escalate = True
        report.append(
            UnsupportedClaimReportItem(
                claim_text=claim.claim_text,
                source=claim.source,
                support_status=status,
                missing_evidence_reason=reason,
                escalation_flag=escalate,
            )
        )
    return report


def _confidence_scores(
    visual: list[VisualIntelligencePlaceholder],
    ocr: list[OcrTextPlaceholder],
    transcript: list[TranscriptEvidencePointer],
) -> ConfidenceScores:
    media_conf = 0.9 if visual else 0.2
    ocr_conf = _avg([o.confidence_score for o in ocr], default=0.0)
    visual_conf = _avg([v.confidence_score for v in visual], default=0.0)
    transcript_conf = _avg([t.confidence for t in transcript], default=0.0)
    final = round((media_conf + ocr_conf + visual_conf + transcript_conf) / 4, 3)
    return ConfidenceScores(
        media_confidence=media_conf,
        ocr_confidence=ocr_conf,
        visual_confidence=visual_conf,
        transcript_confidence=transcript_conf,
        final_evidence_confidence=final,
    )


def _escalation_flags(
    scores: ConfidenceScores,
    report: list[UnsupportedClaimReportItem],
    transcript_evidence: list[TranscriptEvidencePointer],
    visual_evidence: list[VisualEvidencePointer],
) -> EscalationFlags:
    missing_transcript = not transcript_evidence or any(i.support_status == "unsupported" and i.source in {"transcript", "generated"} for i in report)
    missing_visual = not visual_evidence or any(i.support_status == "unsupported" and i.source == "visual" for i in report)
    low_ocr = scores.ocr_confidence < LOW_OCR_THRESHOLD
    possible_hallucination = any(i.support_status in {"unsupported", "needs_review"} for i in report)
    human_review = missing_transcript or missing_visual or low_ocr or possible_hallucination or scores.final_evidence_confidence < FINAL_APPROVAL_THRESHOLD
    return EscalationFlags(
        missing_transcript_evidence=missing_transcript,
        missing_visual_evidence=missing_visual,
        low_ocr_confidence=low_ocr,
        possible_hallucination=possible_hallucination,
        human_review_required=human_review,
    )


def _evidence_gate(inp: VisualEvidenceInput, scores: ConfidenceScores, flags: EscalationFlags, report: list[UnsupportedClaimReportItem]) -> EvidenceGateOutput:
    reasons: list[str] = []
    if flags.missing_transcript_evidence:
        reasons.append("missing_transcript_evidence")
    if flags.missing_visual_evidence:
        reasons.append("missing_visual_evidence")
    if flags.low_ocr_confidence:
        reasons.append("low_ocr_confidence")
    if flags.possible_hallucination:
        reasons.append("possible_hallucination")
    if scores.final_evidence_confidence < FINAL_APPROVAL_THRESHOLD:
        reasons.append("final_evidence_confidence_below_approval_threshold")

    unsupported = any(i.support_status == "unsupported" for i in report)
    gate = "hold" if unsupported or flags.human_review_required else "approve"
    if gate == "approve" and scores.final_evidence_confidence < FINAL_APPROVAL_THRESHOLD:
        gate = "review"
    blocked = inp.hosted_manifest_candidate.publishability_gate == "approve" and gate != "approve"
    return EvidenceGateOutput(
        input_hosted_manifest_gate=inp.hosted_manifest_candidate.publishability_gate,
        hosted_manifest_publishability_gate=gate,
        gate=gate,
        approval_without_evidence_blocked=blocked,
        reasons=reasons,
    )


def run_visual_evidence_squad(raw_input: dict) -> dict:
    """Return a deterministic visual/evidence package as plain JSON-ready dict."""
    inp = VisualEvidenceInput.model_validate(raw_input)
    visual = _build_visual_intelligence(inp)
    ocr = _build_ocr(inp)
    entities = _build_entities(inp)
    visual_evidence = _build_visual_evidence(visual)
    transcript_evidence = _build_transcript_evidence(inp)
    report = _build_claim_report(inp, transcript_evidence)
    scores = _confidence_scores(visual, ocr, transcript_evidence)
    flags = _escalation_flags(scores, report, transcript_evidence, visual_evidence)
    gate = _evidence_gate(inp, scores, flags, report)
    output = VisualEvidenceSquadOutput(
        media_id=inp.media_id,
        visual_intelligence=visual,
        ocr_text=ocr,
        entities=entities,
        visual_evidence=visual_evidence,
        transcript_evidence=transcript_evidence,
        unsupported_claim_report=report,
        confidence_scores=scores,
        escalation_flags=flags,
        evidence_gate=gate,
    )
    return output.model_dump(mode="json")
