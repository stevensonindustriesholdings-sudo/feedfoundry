"""Pydantic schemas reject unknown fields (strict bundle contracts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai.feedfoundry_agents.schemas import FeedFoundryJobInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_schemas_strictness_rejects_unknown_fields() -> None:
    base = json.loads((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    base["unexpected_top_level_field"] = "nope"
    with pytest.raises(ValidationError):
        FeedFoundryJobInput.model_validate(base)


def test_feedfoundry_agents_schemas_strictness_nested_segment() -> None:
    base = json.loads((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    base["transcript"]["segments"][0]["extra_seg_field"] = 1
    with pytest.raises(ValidationError):
        FeedFoundryJobInput.model_validate(base)
