"""Orchestrator for the Trenderly Hyperframes video ad squad."""

from __future__ import annotations

from ai.feedfoundry_agents.hyperframes_ads.agents import (
    run_gfx_layer_agent,
    run_hyperframes_manifest_agent,
    run_pod_haul_storyboard_agent,
    run_trend_brief_agent,
    run_trend_logo_agent,
    run_video_safety_agent,
)
from ai.feedfoundry_agents.hyperframes_ads.schemas import (
    AgentRunMeta,
    TrenderlyHyperframesAdInput,
    TrenderlyHyperframesAdOutput,
)


SCHEDULED_AGENTS = [
    "trend_brief_agent",
    "trend_logo_agent",
    "pod_haul_storyboard_agent",
    "gfx_layer_agent",
    "hyperframes_manifest_agent",
    "video_safety_agent",
]


def run_trenderly_hyperframes_ad_squad(job: TrenderlyHyperframesAdInput) -> TrenderlyHyperframesAdOutput:
    """Build an offline Hyperframes request bundle for an approved/held trend.

    The output is safe to persist for operator review. It does not call Hyperframes,
    OpenAI, or any external provider; live execution belongs behind explicit budget
    reservation and provider routing gates.
    """

    trend_brief = run_trend_brief_agent(job)
    trend_logo = run_trend_logo_agent(job, trend_brief)
    storyboard = run_pod_haul_storyboard_agent(job, trend_brief)
    gfx_layers = run_gfx_layer_agent(job, trend_brief, trend_logo, storyboard)
    hyperframes_plan = run_hyperframes_manifest_agent(job, storyboard, trend_logo, gfx_layers)
    safety = run_video_safety_agent(job, trend_brief, hyperframes_plan)
    return TrenderlyHyperframesAdOutput(
        run=AgentRunMeta(agents_scheduled=SCHEDULED_AGENTS),
        trend_brief=trend_brief,
        trend_logo=trend_logo,
        storyboard=storyboard,
        gfx_layers=gfx_layers,
        hyperframes_plan=hyperframes_plan,
        safety=safety,
    )
