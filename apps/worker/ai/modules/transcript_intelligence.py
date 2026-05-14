"""Transcript intelligence: chunked transcript → mock provider → validated contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from ai.chunking import chunk_transcript_text
from ai.modules.output_validator import OutputValidator, ValidationResult, ValidationStatus
from ai.provider import AIProvider
from ai.registry import get_structured_ai_provider
from ai.schemas.output_contracts import (
    CHAPTERS_SCHEMA_NAME,
    CHAPTERS_SCHEMA_VERSION,
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    FAQ_SCHEMA_NAME,
    FAQ_SCHEMA_VERSION,
    METADATA_SCHEMA_NAME,
    METADATA_SCHEMA_VERSION,
)
from ai.transcript_context import EvidencePointer, TranscriptChunkInput
from ai.types import AICompletionRequest

STAGE_NAME = "transcript_intelligence"

_SCHEMA_SEQUENCE: tuple[tuple[str, str], ...] = (
    (FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION),
    (FAQ_SCHEMA_NAME, FAQ_SCHEMA_VERSION),
    (CHAPTERS_SCHEMA_NAME, CHAPTERS_SCHEMA_VERSION),
    (METADATA_SCHEMA_NAME, METADATA_SCHEMA_VERSION),
)


@dataclass(frozen=True)
class ValidatedTranscriptArtifact:
    """One schema-validated payload with transcript provenance (no raw prose path)."""

    evidence: EvidencePointer
    schema_name: str
    schema_version: str
    validation: ValidationResult


class TranscriptIntelligenceValidationError(RuntimeError):
    """Raised when the mock provider JSON fails ``OutputValidator`` for a chunk/schema pair."""


def describe() -> str:
    return "Transcript intelligence: extract structured knowledge from chunked transcript text."


def chunks_from_plain_text(
    text: str,
    *,
    max_chars: int,
    overlap: int,
) -> list[TranscriptChunkInput]:
    """Build ``TranscriptChunkInput`` rows using ``chunk_transcript_text`` (char windows)."""
    windows = chunk_transcript_text(text, max_chars=max_chars, overlap=overlap)
    out: list[TranscriptChunkInput] = []
    for idx, (_, _, piece) in enumerate(windows):
        out.append(TranscriptChunkInput(chunk_index=idx, text=piece, start_ms=None, end_ms=None))
    return out


def _input_bundle_for_chunk(chunk: TranscriptChunkInput, *, episode_title: str | None) -> dict[str, Any]:
    return {
        "chunk_index": chunk.chunk_index,
        "transcript_text": chunk.text,
        "segment_id": chunk.segment_id,
        "start_ms": chunk.start_ms,
        "end_ms": chunk.end_ms,
        "episode_title": episode_title,
    }


def run_transcript_intelligence(
    chunks: Sequence[TranscriptChunkInput],
    *,
    job_id: str,
    provider: AIProvider | None = None,
    validator: OutputValidator | None = None,
    episode_title: str | None = None,
    prompt_version: str = "p7-transcript-intelligence-1",
    model: str = "mock",
) -> list[ValidatedTranscriptArtifact]:
    """Run factsheet / FAQ / chapters / metadata for each chunk through mock → ``OutputValidator``.

    Deterministic under ``MockAIProvider``; rejects are surfaced as
    ``TranscriptIntelligenceValidationError`` (no unvalidated customer-visible payloads).
    """
    if not chunks:
        return []

    prov = provider or get_structured_ai_provider()
    val = validator or OutputValidator()

    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    first_title = episode_title
    if first_title is None and ordered:
        first_title = (ordered[0].text[:80] + "…") if len(ordered[0].text) > 80 else ordered[0].text

    results: list[ValidatedTranscriptArtifact] = []
    for chunk in ordered:
        evidence = EvidencePointer.from_chunk(chunk)
        bundle = _input_bundle_for_chunk(chunk, episode_title=first_title)
        for schema_name, schema_version in _SCHEMA_SEQUENCE:
            req = AICompletionRequest(
                stage_name=STAGE_NAME,
                schema_name=schema_name,
                schema_version=schema_version,
                prompt_version=prompt_version,
                model=model,
                input_bundle=bundle,
                max_tokens=512,
                temperature=0.0,
                timeout_seconds=30,
                cost_cap=0.0,
                trace_id=f"{job_id}:ti:{chunk.chunk_index}:{schema_name}",
            )
            parsed = prov.complete(req).parsed_json
            vres = val.validate_payload(schema_name=schema_name, schema_version=schema_version, payload=parsed)
            if vres.status != ValidationStatus.ACCEPTED:
                raise TranscriptIntelligenceValidationError(
                    f"chunk={chunk.chunk_index} schema={schema_name} status={vres.status} errors={vres.errors}"
                )
            results.append(
                ValidatedTranscriptArtifact(
                    evidence=evidence,
                    schema_name=schema_name,
                    schema_version=schema_version,
                    validation=vres,
                )
            )
    return results


def iter_accepted_models(artifacts: Iterable[ValidatedTranscriptArtifact]) -> list[Any]:
    """Helper for callers that need concrete Pydantic instances (all ACCEPTED in normal runs)."""
    return [a.validation.model for a in artifacts if a.validation.model is not None]
