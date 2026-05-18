"""Hyperframes client boundary.

The planning squad emits request JSON only. This client exists so future Railway
workers/operators have one explicit place to plug in a live Hyperframes endpoint,
with budget reservation and provider routing handled before this code is called.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ai.feedfoundry_agents.hyperframes_ads.schemas import HyperframesRenderRequest


class HyperframesDisabledError(RuntimeError):
    """Raised when code attempts a live render without explicit enablement."""


@dataclass(frozen=True)
class HyperframesClientConfig:
    endpoint: str | None = None
    api_key: str | None = None
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "HyperframesClientConfig":
        return cls(
            endpoint=os.getenv("HYPERFRAMES_API_BASE_URL"),
            api_key=os.getenv("HYPERFRAMES_API_KEY"),
            enabled=os.getenv("HYPERFRAMES_LIVE_RENDER_ENABLED", "").lower() in {"1", "true", "yes"},
        )


class HyperframesClient:
    """Small env-gated adapter for future live render calls."""

    def __init__(self, config: HyperframesClientConfig | None = None) -> None:
        self.config = config or HyperframesClientConfig.from_env()

    def build_payload(self, request: HyperframesRenderRequest) -> dict[str, Any]:
        return request.model_dump(mode="json", by_alias=True)

    def submit_render(self, request: HyperframesRenderRequest) -> dict[str, Any]:
        """Submit a live render only when explicitly enabled.

        This method intentionally does not import httpx unless it is about to make a
        live call. Tests and local dev stay offline by default.
        """

        if not self.config.enabled:
            raise HyperframesDisabledError(
                "Live Hyperframes rendering is disabled. Set HYPERFRAMES_LIVE_RENDER_ENABLED=true "
                "after credits are reserved and operator approval is recorded."
            )
        if not self.config.endpoint or not self.config.api_key:
            raise HyperframesDisabledError("HYPERFRAMES_API_BASE_URL and HYPERFRAMES_API_KEY are required.")

        import httpx

        response = httpx.post(
            f"{self.config.endpoint.rstrip('/')}/renders",
            json=self.build_payload(request),
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
