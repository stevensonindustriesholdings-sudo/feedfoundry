"""GEO freshness defaults to static fixture mode; live flag only changes mode label."""

from __future__ import annotations

import os
from pathlib import Path

from ai.feedfoundry_agents.agents.geo_freshness import run_geo_freshness
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_geo_freshness_static_default(monkeypatch) -> None:
    monkeypatch.delenv("FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED", raising=False)
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    out = run_geo_freshness(job)
    assert out.mode == "static_fixture"
    assert out.live_research_requested is False
    assert out.citations[0].source == "fixture_seed"


def test_feedfoundry_agents_geo_freshness_flag_requests_live_stub(monkeypatch) -> None:
    monkeypatch.setenv("FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED", "true")
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    out = run_geo_freshness(job)
    assert out.mode == "live_requested_stubbed"
    assert out.live_research_requested is True
