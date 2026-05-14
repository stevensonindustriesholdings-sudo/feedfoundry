"""Phase 7 AI Captain / orchestrator skeleton (bounded plans, no free-running loops)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ai.provider import AIProvider
from ai.registry import get_structured_ai_provider
from ai.types import AICompletionRequest, AICompletionResponse


@dataclass
class AICaptain:
    """Builds a static stage list and executes each stage through a provider (skeleton)."""

    provider: AIProvider | None = None
    _stages: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.provider is None:
            self.provider = get_structured_ai_provider()
        # Default plan: module stubs registration order (expand in later slices).
        if not self._stages:
            self._stages = [
                "transcript_intelligence",
                "visual_analyst",
                "product_signal",
                "verifier",
                "governor",
                "output_validator",
            ]

    def default_stages(self) -> tuple[str, ...]:
        return tuple(self._stages)

    def run_plan(
        self,
        *,
        job_id: str,
        input_bundle: dict,
        schema_name: str = "ai.stub.v1",
        schema_version: str = "0.1.0",
        prompt_version: str = "p7-skeleton-1",
        model: str = "mock",
    ) -> list[AICompletionResponse]:
        """Execute each stage with a minimal bounded request (deterministic under mock)."""
        out: list[AICompletionResponse] = []
        assert self.provider is not None
        for stage in self._stages:
            req = AICompletionRequest(
                stage_name=stage,
                schema_name=schema_name,
                schema_version=schema_version,
                prompt_version=prompt_version,
                model=model,
                input_bundle={**input_bundle, "job_id": job_id},
                max_tokens=256,
                temperature=0.0,
                timeout_seconds=30,
                cost_cap=0.0,
                trace_id=f"{job_id}:{stage}",
            )
            out.append(self.provider.complete(req))
        return out
