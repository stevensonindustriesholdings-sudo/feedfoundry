# FeedFoundry — Railway / AI worker demo lane

**Branch:** `feat/feedfoundry-railway-ai-worker-demo`  
**Date:** 2026-05-17

## What shipped

- **YouTube URL queue (enqueue only):** `POST /v1/youtube-source-queue` with `{ "youtube_url": "https://..." }` stores a row in `youtube_source_queue` (no download, no scraping, no auth bypass). `GET /v1/youtube-source-queue` lists per org. Admin: `GET /v1/admin/youtube-queue`.
- **System hints:** `GET /v1/system/worker-hints` returns booleans only (`ff_ai_live_calls_enabled`, provider key *configured* flags, module count). No secrets in JSON.
- **Worker AI probe:** On each job, `apps/worker/ai_router_probe.py` logs a **mock** router line unless `FF_AI_LIVE_CALLS_ENABLED` is truthy and OpenRouter or OpenAI key is present; then one tiny chat completion is attempted and results are logged (token counts when available, never keys).
- **AI routing:** New `worker_router_probe` module in `ai-routing.yaml` (OpenRouter primary, OpenAI fallback).
- **Web:** Upload page — optional YouTube URL backlog panel. Jobs page — worker/provider mode strip from worker-hints. System page — third panel for worker-hints.

## DB

- Alembic `007_youtube_source_queue` creates `youtube_source_queue` (PostgreSQL path; SQLite dev uses metadata where applicable).

## Railway / staging

- **CLI:** `railway 4.58.0`, logged in; `railway status` **Abort trap: 6** on this host — treat as local CLI bug; use dashboard or `railway logs` for service state.
- **Deploy:** No agent push (per sprint). If GitHub ↔ Railway auto-deploy is linked, merge these branches to the tracked branch for **api-v2-IQho** / **worker-v2** only (workspace allowlist).
- **Env (document only):** `FF_AI_LIVE_CALLS_ENABLED`, `OPENROUTER_API_KEY`, `OPENROUTER_ROUTER_PROBE_MODEL`, `OPENAI_API_KEY` — set in Railway, never in repo.

## Tests run (targeted)

- `python3 -m pytest apps/api/tests/test_credit_ledger.py` — PASS (6).
- `npm run typecheck` in `apps/web` — PASS.

## Honest blockers

- Full API import on a bare macOS Python without venv may fail on optional `stripe` — use project venv / Docker for local OpenAPI smoke.

## Next

- Run `alembic upgrade head` against staging Postgres before relying on the YouTube queue table.
- Toggle `FF_AI_LIVE_CALLS_ENABLED=1` on **worker-v2** only after keys are in Railway and budget policy is confirmed.
