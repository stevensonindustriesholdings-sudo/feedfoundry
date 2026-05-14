"""Strip internal-only fields before writing customer-facing JSON to object storage."""

from __future__ import annotations

from typing import Any

from pipeline.transcript_derived_outputs import _clean_display_text, _transcript_origin_label


def transcript_json_for_customer(internal: dict[str, Any] | None) -> dict[str, Any] | None:
    """Public ``raw_transcript`` shape: segments + schema; no ffmpeg meta or provider diagnostics."""
    if internal is None:
        return None
    segments: list[dict[str, Any]] = []
    for seg in internal.get("segments") or []:
        try:
            start = float(seg.get("start", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = float(seg.get("end", start))
        except (TypeError, ValueError):
            end = start
        text = _clean_display_text((seg.get("text") or "").strip())
        segments.append({"start": start, "end": end, "text": text})
    return {
        "schema_version": str(internal.get("schema_version") or "1.0"),
        "source": _transcript_origin_label(internal),
        "segments": segments,
    }


def media_inspection_json_for_customer(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop worker-only planning fields (e.g. chunk indices) from published media inspection."""
    if payload is None:
        return None
    out = {k: v for k, v in payload.items() if k != "chunk_plan"}
    return out
