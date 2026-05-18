"""Trenderly POD-haul Hyperframes video ad squad.

This package is deterministic/offline by default. Live Hyperframes calls are kept
behind an explicit client boundary so the worker can plan, estimate credits, and
emit manifests without exposing keys or spending provider credits implicitly.
"""

from ai.feedfoundry_agents.hyperframes_ads.orchestrator import run_trenderly_hyperframes_ad_squad
from ai.feedfoundry_agents.hyperframes_ads.schemas import (
    HyperframesRenderRequest,
    TrenderlyHyperframesAdOutput,
    TrenderlyHyperframesAdInput,
)

__all__ = [
    "HyperframesRenderRequest",
    "TrenderlyHyperframesAdInput",
    "TrenderlyHyperframesAdOutput",
    "run_trenderly_hyperframes_ad_squad",
]
