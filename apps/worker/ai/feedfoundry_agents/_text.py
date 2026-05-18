"""Combine transcript text for deterministic derivations."""

from __future__ import annotations

from ai.feedfoundry_agents.schemas import FeedFoundryJobInput


def combined_transcript_text(job: FeedFoundryJobInput, *, max_chars: int = 4000) -> str:
    parts: list[str] = []
    for seg in job.transcript.segments:
        t = (seg.text or "").strip()
        if t:
            parts.append(t)
    blob = " ".join(parts).strip()
    if len(blob) > max_chars:
        return blob[: max_chars - 1].rstrip() + "…"
    return blob or "Episode"
