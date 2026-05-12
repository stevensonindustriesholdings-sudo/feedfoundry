from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AudioChunk:
    index: int
    start_sec: float
    end_sec: float


def plan_chunks(duration_seconds: float, chunk_seconds: float = 600.0) -> list[AudioChunk]:
    if duration_seconds <= 0:
        return [AudioChunk(0, 0.0, min(chunk_seconds, 60.0))]
    chunks: list[AudioChunk] = []
    start = 0.0
    idx = 0
    while start < duration_seconds:
        end = min(start + chunk_seconds, duration_seconds)
        chunks.append(AudioChunk(idx, start, end))
        idx += 1
        start = end
    return chunks
