from __future__ import annotations

from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, TranscriptStewardOutput


def run_transcript_steward(job: FeedFoundryJobInput) -> TranscriptStewardOutput:
    segs = job.transcript.segments
    anomalies: list[str] = []
    for i, s in enumerate(segs):
        if s.end < s.start:
            anomalies.append(f"segment_{i}_end_before_start")
        if not (s.text or "").strip():
            anomalies.append(f"segment_{i}_empty_text")
    return TranscriptStewardOutput(segment_count=len(segs), anomalies=anomalies)
