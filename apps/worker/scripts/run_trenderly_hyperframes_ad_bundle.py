"""Run the deterministic Trenderly Hyperframes ad squad against a JSON input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from ai.feedfoundry_agents.hyperframes_ads.orchestrator import run_trenderly_hyperframes_ad_squad
from ai.feedfoundry_agents.hyperframes_ads.schemas import TrenderlyHyperframesAdInput


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a draft Trenderly Hyperframes POD-haul ad bundle.")
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    job = TrenderlyHyperframesAdInput.model_validate_json(args.input_json.read_text(encoding="utf-8"))
    output = run_trenderly_hyperframes_ad_squad(job)
    payload = json.dumps(output.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
