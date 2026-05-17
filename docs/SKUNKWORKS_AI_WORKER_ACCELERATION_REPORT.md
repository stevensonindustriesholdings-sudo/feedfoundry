# Skunk Works AI worker acceleration — FeedFoundry lane report

**Date:** 2026-05-17  
**Branch:** `feat/skunkworks-ai-worker-acceleration`  
**Constraints:** No Stripe/credit semantics changes, no live paid AI in this commit, no Railway/production mutation, no `git push` from agent.

## Executive summary

FeedFoundry already routes AI through the API-layer YAML + `apps/api/app/services/ai_router.py` and worker-local mocks. This lane adds a **documentation-first bridge** to Stevenson CEO shared contracts (`vendor/stevenson-contracts/`, `apps/worker/skunkworks_contract_bridge.py`) and **FF_AI_*** environment placeholders aligned with `@stevenson/si-ai-routing` naming, without wiring a hard Node dependency into Python.

## Checklist

| Item | Status |
|------|--------|
| Phase 7 worker skeleton reviewed (`apps/worker/worker.py`, `apps/api/tests/test_ai_router.py`) | **Documented** — worker remains Postgres/R2 FFmpeg spine |
| CEO contract snapshot vendored | **Done** — `vendor/stevenson-contracts/product_template_ids.v1.json` |
| Optional Python loader (no import side effects) | **Done** — `apps/worker/skunkworks_contract_bridge.py` |
| `.env.example` FF_AI_* placeholders | **Done** |
| Companion docs (YouTube authorised ingest, Railway AI readiness, product grid) | **Done** — see `docs/YOUTUBE_CREATOR_AUTHORISED_INGEST_PATH.md`, `docs/RAILWAY_AI_READINESS.md`, `docs/PRODUCT_GRID_LAUNCH.md` |
| `apps/web` typecheck | Run: `cd apps/web && npm run typecheck` |
| `python -m pytest` | Run from API package: `cd apps/api && python3 -m pytest` (or project venv) |

## Integration notes

- **Path / file URL:** Prefer vendored JSON in-repo. Optional dev checkout: clone CEO repo and diff `packages/si-video-composition/schemas/` against `vendor/stevenson-contracts/` when contracts change.
- **Runtime:** Do not import CEO TypeScript from Python. Refresh snapshots deliberately after CEO semver/tag decisions.

## Next steps (product)

1. Map `RenderManifestV1` fields to `JobOutput` JSON blobs when Hyperframes export lands in worker pipeline.
2. Keep OpenRouter / external LLM calls behind existing AI router + ledger gates.
