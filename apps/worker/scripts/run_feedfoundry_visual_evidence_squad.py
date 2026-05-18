#!/usr/bin/env python3
"""Optional CLI smoke for the deterministic FeedFoundry visual/evidence squad."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.feedfoundry_agents.visual_evidence.orchestrator import run_visual_evidence_squad  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic FeedFoundry visual/evidence squad.")
    parser.add_argument(
        "input_json",
        nargs="?",
        default=str(ROOT / "tests" / "fixtures" / "feedfoundry_visual_evidence" / "tiny_visual_evidence_input.json"),
        help="Path to visual evidence fixture/input JSON",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        default=str(ROOT / "artifacts" / "feedfoundry-visual-evidence"),
        help="Output directory for visual_evidence.json",
    )
    args = parser.parse_args()

    raw = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    package = run_visual_evidence_squad(raw)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "visual_evidence.json"
    out_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "ok": True,
        "output": str(out_path),
        "media_id": package["media_id"],
        "visual_evidence_count": len(package["visual_evidence"]),
        "ocr_count": len(package["ocr_text"]),
        "unsupported_claim_count": sum(
            1 for item in package["unsupported_claim_report"] if item["support_status"] == "unsupported"
        ),
        "human_review_required": package["escalation_flags"]["human_review_required"],
        "hosted_manifest_publishability_gate": package["evidence_gate"]["hosted_manifest_publishability_gate"],
        "execution_mode": package["execution_mode"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
