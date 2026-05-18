"""Schema.org agent emits JSON-LD with expected @context."""

from __future__ import annotations

from pathlib import Path

from ai.feedfoundry_agents.agents.schema_org import run_schema_org_specialist
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_schema_org() -> None:
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    out = run_schema_org_specialist(job)
    assert out.json_ld["@context"] == "https://schema.org"
    assert "PodcastEpisode" in out.json_ld["@type"]
