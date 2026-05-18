from __future__ import annotations

from ai.feedfoundry_agents._text import combined_transcript_text
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, MetadataCuratorOutput


def run_metadata_curator(job: FeedFoundryJobInput) -> MetadataCuratorOutput:
    blob = combined_transcript_text(job, max_chars=500)
    title = (job.original_basename or "episode").rsplit(".", 1)[0].replace("_", " ")
    topics = job.product_context.primary_topics[:8]
    return MetadataCuratorOutput(
        youtube={
            "title": title[:100],
            "description": blob[:400],
            "keywords": topics,
        },
        podcast={
            "title": title[:100],
            "summary": blob[:400],
            "episodeType": "full",
        },
    )
