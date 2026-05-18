"""FeedFoundry Hermes-style agent bundle (v0.1 deterministic implementation)."""

from ai.feedfoundry_agents.schemas import FeedFoundryAgentBundleOutput, FeedFoundryJobInput

__all__ = ["FeedFoundryJobInput", "FeedFoundryAgentBundleOutput", "run_feedfoundry_agent_bundle"]


def __getattr__(name: str):
    if name == "run_feedfoundry_agent_bundle":
        from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle as fn

        return fn
    raise AttributeError(name)
