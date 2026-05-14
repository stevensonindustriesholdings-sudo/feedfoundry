from __future__ import annotations

import math
from pathlib import Path
from typing import Any, List, Optional

import yaml

from app.schemas.outputs import ApiRequestedOutput


def load_routing_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def estimate_job_processing_minutes(
    *,
    routing_path: Path,
    requested_outputs: List[str],
    media_duration_seconds: Optional[float],
) -> int:
    """Upper-bound processing minutes from ai-routing module ceilings + transcribe hourly rate."""
    cfg = load_routing_config(routing_path)
    modules: dict[str, Any] = cfg.get("modules") or {}
    hours = (media_duration_seconds or 3600) / 3600.0
    total = 0.0

    wants_transcript = ApiRequestedOutput.TRANSCRIPT.value in requested_outputs
    if wants_transcript:
        tr = modules.get("transcribe") or {}
        per_hour = float(tr.get("cost_ceiling_credits_per_media_hour") or 0)
        total += per_hour * max(hours, 0.01)

    module_by_output: dict[str, str] = {
        ApiRequestedOutput.CLEAN_TRANSCRIPT.value: "transcript_cleaner",
        ApiRequestedOutput.CHAPTERS.value: "chapters",
        ApiRequestedOutput.SHOW_NOTES.value: "show_notes",
        ApiRequestedOutput.METADATA.value: "metadata",
        ApiRequestedOutput.FACT_SHEET.value: "fact_sheet",
        ApiRequestedOutput.FAQS.value: "faqs",
        ApiRequestedOutput.CTAS.value: "ctas",
        ApiRequestedOutput.HOSTED_MANIFEST.value: "hosted_manifest",
    }

    for out in requested_outputs:
        mod_name = module_by_output.get(out)
        if not mod_name:
            continue
        mod = modules.get(mod_name) or {}
        ceiling = mod.get("cost_ceiling_credits")
        if ceiling is not None:
            total += float(ceiling)

    if ApiRequestedOutput.EXPORT_BUNDLE.value in requested_outputs:
        total += 1.0

    if ApiRequestedOutput.CLIP_CANDIDATES.value in requested_outputs:
        total += float((modules.get("chapters") or {}).get("cost_ceiling_credits") or 2)

    return max(1, int(math.ceil(total)))


# Legacy name (YAML still uses cost_ceiling_credits_* knobs as internal ceilings).
estimate_job_credits = estimate_job_processing_minutes
