from __future__ import annotations

from ai.feedfoundry_agents._text import combined_transcript_text
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput, HostedManifestHintsOutput


def run_hosted_manifest_composer(job: FeedFoundryJobInput) -> HostedManifestHintsOutput:
    summary = combined_transcript_text(job, max_chars=720)
    title = (job.original_basename or "episode").rsplit(".", 1)[0].replace("_", " ").strip().title()
    topics = job.product_context.primary_topics[:16]
    meta_title = f"{title} | {job.creator_slug}"
    meta_desc = summary[:155]
    outputs = [
        "transcript.json",
        "chapters.json",
        "factsheet.json",
        "faq.json",
        "metadata.json",
        "ctas.json",
        "hosted_manifest.json",
        "export_bundle.json",
    ]
    return HostedManifestHintsOutput(
        canonical_title=title[:160],
        summary=summary or "Summary derived from transcript (deterministic mock).",
        outputs_available=outputs,
        seo_meta_title=meta_title[:120],
        seo_meta_description=meta_desc,
        keywords=topics,
    )
