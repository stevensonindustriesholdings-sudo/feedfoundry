from __future__ import annotations

from ai.feedfoundry_agents._text import combined_transcript_text
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, ShowNotesOutput


def run_show_notes_writer(job: FeedFoundryJobInput) -> ShowNotesOutput:
    blob = combined_transcript_text(job, max_chars=800)
    title = job.product_context.show_name or job.creator_slug
    bullets = [
        f"Episode focus: {blob[:200]}".rstrip("…"),
        "Timestamps align with transcript segments (deterministic mock).",
    ]
    return ShowNotesOutput(title=title[:120], bullets=bullets, resources=[])
