"""Visual analysis: visual context → mock provider → ``OutputValidator`` (no raw prose path).

Guardrails
----------
Outputs are schema-bound only. The mock provider must not fabricate definitive
on-screen commerce claims, external URLs, or OCR beyond supplied snippets.
"""

from __future__ import annotations

from typing import Any

from ai.modules.output_validator import OutputValidator, ValidationResult, ValidationStatus
from ai.provider import AIProvider
from ai.registry import get_structured_ai_provider
from ai.schemas.output_contracts import VISUAL_ANALYSIS_REPORT_SCHEMA_NAME, VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION
from ai.types import AICompletionRequest
from ai.visual_context import VisualAnalysisContext

STAGE_NAME = "visual_analysis"


class VisualAnalysisValidationError(RuntimeError):
    """Raised when mock JSON fails ``OutputValidator`` for ``VisualAnalysisReport``."""


def describe() -> str:
    return "Visual analysis: keyframes, OCR snippets, evidence links — validated structured report."


def _fallback_scene_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    kfs = bundle.get("keyframes") or []
    if isinstance(kfs, list) and kfs and isinstance(kfs[0], dict):
        fr = kfs[0].get("frame_id", "frame-0")
        t_ms = int(kfs[0].get("t_ms", 0))
        return {"label": f"Keyframe {fr}", "start_ms": t_ms, "end_ms": t_ms + 1}
    return {"label": "Visual scene (no keyframes supplied)", "start_ms": 0, "end_ms": 1}


def run_visual_analysis(
    ctx: VisualAnalysisContext,
    *,
    job_id: str,
    provider: AIProvider | None = None,
    validator: OutputValidator | None = None,
    prompt_version: str = "p7-visual-analysis-1",
    model: str = "mock",
) -> tuple[ValidationResult, dict[str, Any]]:
    """Build request, complete via provider, validate ``VisualAnalysisReport``."""
    prov = provider or get_structured_ai_provider()
    val = validator or OutputValidator()
    bundle = dict(ctx.to_input_bundle())
    bundle["scene_fallback"] = _fallback_scene_from_bundle(bundle)
    req = AICompletionRequest(
        stage_name=STAGE_NAME,
        schema_name=VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
        schema_version=VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
        prompt_version=prompt_version,
        model=model,
        input_bundle=bundle,
        max_tokens=768,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id=f"{job_id}:visual_analysis",
    )
    parsed: dict[str, Any] = prov.complete(req).parsed_json
    vres = val.validate_payload(
        schema_name=VISUAL_ANALYSIS_REPORT_SCHEMA_NAME,
        schema_version=VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION,
        payload=parsed,
    )
    if vres.status != ValidationStatus.ACCEPTED:
        raise VisualAnalysisValidationError(f"status={vres.status} errors={vres.errors}")
    return vres, parsed
