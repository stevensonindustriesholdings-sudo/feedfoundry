"""Orchestrator returns a full bundle matching the v0.1 key contract."""

from __future__ import annotations

import json
from pathlib import Path

from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_orchestrator_full_bundle() -> None:
    raw = (FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8")
    job = FeedFoundryJobInput.model_validate_json(raw)
    bundle = run_feedfoundry_agent_bundle(job)
    shape = json.loads((FIXTURE_DIR / "expected_bundle_shape.json").read_text(encoding="utf-8"))
    keys = set(shape["top_level_keys"])
    assert keys == set(bundle.model_dump().keys())
    assert bundle.run.execution_mode == "deterministic_mock"
    assert bundle.judge.verdict.value in ("pass", "pass_with_notes", "blocked")
    assert bundle.geo_freshness.citations[0].source == "fixture_seed"
