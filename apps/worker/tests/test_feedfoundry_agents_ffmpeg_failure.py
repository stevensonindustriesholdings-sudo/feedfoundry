"""FFmpeg failure classifier never debits processing minutes."""

from __future__ import annotations

import json
from pathlib import Path

from ai.feedfoundry_agents.agents.ffmpeg_failure import classify_ffmpeg_failure
from ai.feedfoundry_agents.schemas import FFmpegFailureInput

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_ffmpeg_failure_classifier() -> None:
    data = json.loads((FIXTURE_DIR / "ffmpeg_failure_samples.json").read_text(encoding="utf-8"))
    families: set[str] = set()
    for s in data["samples"]:
        inp = FFmpegFailureInput.model_validate(s)
        out = classify_ffmpeg_failure(inp)
        assert out.debit_processing_minutes is False
        families.add(out.failure_family)
    assert "io_pipe" in families or "demux_decode" in families
