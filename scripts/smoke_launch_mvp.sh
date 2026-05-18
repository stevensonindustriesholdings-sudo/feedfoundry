#!/usr/bin/env bash
# FeedFoundry launch MVP smoke — no secrets printed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Python import (API) =="
cd apps/api
uv run python -c "from app.main import app; print('PASS: api import')"

echo "== Web typecheck + build =="
cd "$ROOT/apps/web"
npm run typecheck
npm run build

echo "== Agent bundle CLI (deterministic) =="
cd "$ROOT/apps/worker"
PYTHONPATH=".:../api" uv run python scripts/run_feedfoundry_agent_bundle.py --out-dir /tmp/ff-agent-bundle-smoke >/dev/null
echo "PASS: agent bundle CLI"

echo "== API tests (intake) =="
cd "$ROOT/apps/api"
uv run pytest tests/test_intake_launch_mvp.py -q

echo "== Worker tests (agent bundle integration) =="
cd "$ROOT/apps/worker"
PYTHONPATH=".:../api" uv run pytest tests/test_feedfoundry_agents_worker_integration.py tests/test_worker_hosted_manifest_agent_bundle.py -q

echo "ALL PASS: smoke_launch_mvp"
