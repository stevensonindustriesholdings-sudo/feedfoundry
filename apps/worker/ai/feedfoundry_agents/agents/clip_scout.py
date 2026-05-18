from __future__ import annotations

from ai.feedfoundry_agents.schemas import ClipCandidateOut, ClipScoutOutput, FeedFoundryJobInput


def run_clip_scout(job: FeedFoundryJobInput) -> ClipScoutOutput:
    clips: list[ClipCandidateOut] = []
    segs = job.transcript.segments
    if len(segs) >= 2:
        s0, s1 = segs[0], segs[1]
        clips.append(
            ClipCandidateOut(
                start_seconds=float(s0.start),
                end_seconds=float(s1.end),
                hook=(s0.text or "")[:120],
                rationale="First two segments — deterministic placeholder window.",
            )
        )
    elif segs:
        s0 = segs[0]
        end = float(s0.end) + 15.0
        clips.append(
            ClipCandidateOut(
                start_seconds=float(s0.start),
                end_seconds=end,
                hook=(s0.text or "")[:120],
                rationale="Single segment extended window (mock).",
            )
        )
    return ClipScoutOutput(clips=clips)
