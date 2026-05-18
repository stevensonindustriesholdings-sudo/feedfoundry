"""GEO / freshness: static fixture path by default; no live web fetches in v0.1."""

from __future__ import annotations

import os
from datetime import date

from ai.feedfoundry_agents.schemas import GeoCitation, GeoFreshnessOutput, FeedFoundryJobInput


def _flag_enabled() -> bool:
    v = os.environ.get("FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED", "false").lower().strip()
    return v in ("1", "true", "yes")


def run_geo_freshness(job: FeedFoundryJobInput) -> GeoFreshnessOutput:
    requested = _flag_enabled()
    today = date.today().isoformat()
    notes = [
        "Deterministic GEO seed — not live web research.",
        "Customer path uses fixtures/static only in v0.1.",
    ]
    if requested:
        notes.append("FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED=true — live fetch intentionally stubbed.")
    return GeoFreshnessOutput(
        mode="live_requested_stubbed" if requested else "static_fixture",
        reviewed_at=today,
        freshness_notes=notes,
        citations=[GeoCitation(label="fixture", source="fixture_seed")],
        live_research_requested=requested,
    )
