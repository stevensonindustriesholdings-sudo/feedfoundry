from __future__ import annotations

from ai.feedfoundry_agents.schemas import CtaDesignerOutput, CtaOut, FeedFoundryJobInput


def run_cta_designer(job: FeedFoundryJobInput) -> CtaDesignerOutput:
    return CtaDesignerOutput(
        ctas=[
            CtaOut(label="Open full transcript", intent="read_transcript", url=None),
            CtaOut(label="View chapters", intent="view_chapters", url=None),
            CtaOut(label="Share this episode", intent="share_episode", url=None),
        ]
    )
