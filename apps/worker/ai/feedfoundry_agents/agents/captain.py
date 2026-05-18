from __future__ import annotations

from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, CaptainOutput
from ai.feedfoundry_agents._text import combined_transcript_text


def run_captain(job: FeedFoundryJobInput) -> CaptainOutput:
    title = (job.original_basename or "episode").rsplit(".", 1)[0].replace("_", " ").strip() or "Episode"
    blob = combined_transcript_text(job, max_chars=1200)
    return CaptainOutput(
        normalised_title=title[:160],
        summary_seed=blob[:400],
        notes=["deterministic_bundle_v0_1", "no_live_ai"],
    )
