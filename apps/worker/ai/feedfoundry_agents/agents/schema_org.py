from __future__ import annotations

from ai.feedfoundry_agents._text import combined_transcript_text
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, SchemaOrgOutput


def run_schema_org_specialist(job: FeedFoundryJobInput) -> SchemaOrgOutput:
    title = (job.original_basename or "episode").rsplit(".", 1)[0].replace("_", " ")
    desc = combined_transcript_text(job, max_chars=300)
    dur = job.media_meta.duration_seconds
    json_ld = {
        "@context": "https://schema.org",
        "@type": ["PodcastEpisode", "VideoObject"],
        "name": title[:160],
        "description": desc,
        "isPartOf": {"@type": "PodcastSeries", "name": job.product_context.show_name or job.creator_slug},
    }
    if dur is not None:
        json_ld["duration"] = f"PT{int(dur)}S"
    return SchemaOrgOutput(json_ld=json_ld)
