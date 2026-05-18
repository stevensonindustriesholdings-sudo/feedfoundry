"""Repository manifest agent emits llms.txt candidates and hosted manifest field list."""

from __future__ import annotations

import json
from pathlib import Path

from ai.feedfoundry_agents.agents.repository_manifest import run_repository_manifest_librarian
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_repo_manifest() -> None:
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    out = run_repository_manifest_librarian(job)
    assert job.creator_slug in out.llms_txt_candidate
    assert "hosted_manifest.json" in out.llms_txt_candidate
    assert "Policy" in out.llms_full_txt_candidate
    assert "canonical_title" in out.hosted_manifest_json_fields
