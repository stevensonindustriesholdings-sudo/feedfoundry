"""Small typed shapes for transcript intelligence (provenance, evidence pointers)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptChunkInput:
    """One transcript slice entering the intelligence pipeline.

    ``chunk_index`` is required and stable across chunking windows; time fields are
    optional when only character-level chunking is available.
    """

    chunk_index: int
    text: str
    segment_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be non-negative")


@dataclass(frozen=True)
class EvidencePointer:
    """Links a structured artifact back to transcript provenance."""

    chunk_index: int
    segment_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None

    @classmethod
    def from_chunk(cls, chunk: TranscriptChunkInput) -> EvidencePointer:
        return cls(
            chunk_index=chunk.chunk_index,
            segment_id=chunk.segment_id,
            start_ms=chunk.start_ms,
            end_ms=chunk.end_ms,
        )
