#!/usr/bin/env python3
"""Optional CLI: load a ``FeedFoundryJobInput`` JSON and write bundle JSON to ``artifacts/``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle  # noqa: E402
from ai.feedfoundry_agents.schemas import FeedFoundryJobInput  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Run deterministic FeedFoundry agent bundle (v0.1 mock).")
    p.add_argument(
        "input_json",
        nargs="?",
        default=str(ROOT / "tests" / "fixtures" / "feedfoundry_agents" / "tiny_job_input.json"),
        help="Path to FeedFoundryJobInput JSON",
    )
    p.add_argument(
        "-o",
        "--out-dir",
        default=str(ROOT / "artifacts" / "feedfoundry-agent-bundle"),
        help="Output directory for bundle.json",
    )
    args = p.parse_args()
    raw = Path(args.input_json).read_text(encoding="utf-8")
    job = FeedFoundryJobInput.model_validate_json(raw)
    bundle = run_feedfoundry_agent_bundle(job)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bundle.json"
    out_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
