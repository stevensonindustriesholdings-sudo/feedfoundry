# FeedFoundry

Creator archive intelligence engine: upload media, process with FFmpeg and AI on Railway, expose structured outputs via a FastAPI service for Base44 and other clients.

Commercial posture is **annual hosted archive access** and a **creator archive** on the engine side: a **processing allowance** measured in **processing minutes** / **processing time** (not monthly subscription SaaS). Customer-facing copy should say **processing allowance**, **included processing minutes**, or **processing hours** — not “credits.”

**Operator runbook (setup, env, Railway, Base44, AI):** [docs/runbook.md](docs/runbook.md)

**Phase 7 — AI Worker Intelligence Layer (planning, not a launch pivot):** canonical brief and build contract:

- [docs/ai-operating-brief.md](docs/ai-operating-brief.md) — production AI modules (Captain, Producer, Visual, Product signals, Verifier, Governor, …) vs **Cursor** build agents.
- [docs/phase7-implementation-checklist.md](docs/phase7-implementation-checklist.md) — merge order, gates, risks.
- [docs/phase7-agent-ownership-map.md](docs/phase7-agent-ownership-map.md) — parallel Cursor lanes A–F, allowed/forbidden paths.
- [docs/phase7-product-grid-extension.md](docs/phase7-product-grid-extension.md) — **Product Grid / product imagery as optional preview/extension** alongside the video/audio/podcast wedge (not ecommerce).
- [docs/phase7-railway-storage-provider-architecture.md](docs/phase7-railway-storage-provider-architecture.md) — Railway as baseline host only; **worker holds AI provider keys**; **no AI keys in the browser**; S3-compatible storage; mock-provider-first tests for new AI plumbing.
- [docs/phase7-mock-ai-worker-pipeline.md](docs/phase7-mock-ai-worker-pipeline.md) — optional worker mock AI enrichment (`FF_WORKER_AI_ENRICHMENT_ENABLED`), `AIRun` / `AIStageLog`, internal vs customer processing minutes.
- [docs/phase7-openai-canary.md](docs/phase7-openai-canary.md) — structured worker AI modes (`mock` / `canary` / `disabled`), kill-switch env, fail-closed gates (no production rollout in this slice).

**Rule:** new AI worker code paths must be **mock-provider-first** in CI until Captain explicitly enables real provider wiring.

## Repository layout

- `apps/web` — Next.js customer app (proxy to API, no secrets in browser)
- `apps/worker` — polling worker and processing pipeline (Postgres job claims, R2 output writes)
- `packages/schemas` — JSON Schema for hosted manifest, output bundle, AI config
- `scripts/seed_dev.py` — dev org, user, annual access, wallet, demo media asset
- `infra/railway` — Railway deployment hints
- `prompts/system` — system prompts for AI modules
- `docs` — [runbook](docs/runbook.md), technical spec, API contract, Railway deployment
- `alembic` (under `apps/api/alembic`) — database migrations (Postgres in production; `001_initial` bootstraps schema from SQLModel metadata)

## Local development (exact path)

From the **repository root** (`feedfoundry/`):

### 1. Create a virtualenv and install API dependencies

Use a venv under **`apps/api/.venv`** (shared convention for API + worker imports). Hatchling editable installs may require a recent `pip`. If `pip install -e "apps/api[dev]"` fails, install production deps from the same file the Docker image uses, then dev tools:

```bash
python3 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install -U pip
pip install -r apps/api/requirements.txt pytest ruff
```

### 2. Configure environment

```bash
cp .env.example .env.local
# Set DATABASE_URL, FF_INTERNAL_API_KEY, and R2 variables (see below)
```

- **R2 / S3-compatible storage**: set `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_SOURCE`, `R2_BUCKET_OUTPUTS`. The API builds the endpoint as `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` (see `app/settings.py`).
- **Worker without a real upload** (dev only): set `FF_SKIP_SOURCE_VERIFY=true` so the worker does not `HEAD` the source object before processing.

### 3. Run migrations (Postgres or local DB)

Migrations live in `apps/api/alembic/`. From repo root:

```bash
export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/feedfoundry
cd apps/api
PYTHONPATH=. alembic -c alembic.ini upgrade head
cd ../..
```

The initial revision creates all tables from the current SQLModel metadata. **Production and Railway** should always run `alembic upgrade head` instead of relying on ad-hoc `create_all`.

### 4. Seed a usable dev org (Postgres / same `DATABASE_URL`)

```bash
export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/feedfoundry
PYTHONPATH=apps/api python scripts/seed_dev.py
```

This creates (idempotent where possible) `org_dev_demo`, active annual access (`creator_core` / **300 included processing minutes** on the internal wallet from the routing pack), a wallet, an `annual_grant` transaction with idempotency key `ff:seed_dev:annual_grant`, and a demo `MediaAsset` `ma_dev_demo` with slugs `demo-creator` / `episode-001`.

**Production guard:** the script exits unless `ALLOW_DEV_SEED=true` when `APP_ENV` is `production` or `prod`. Never set `ALLOW_DEV_SEED` on a real production database unless you explicitly intend to insert demo data.

### 5. Start the API

```bash
source apps/api/.venv/bin/activate
cd apps/api
export DATABASE_URL=...   # same as above
export FF_INTERNAL_API_KEY=replace_me
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start the worker (separate terminal)

```bash
source apps/api/.venv/bin/activate
pip install -r apps/worker/requirements.txt
export DATABASE_URL=...   # same database
# Same R2 env vars as the API; optional for local:
export FF_SKIP_SOURCE_VERIFY=true
cd apps/worker
PYTHONPATH=../api:. python worker.py
```

`PYTHONPATH` must include `apps/api` so the worker can import `app.*` and share the processing-minute ledger.

### 7. Run tests

```bash
cd apps/api && source .venv/bin/activate && python -m pytest -q
cd ../worker && PYTHONPATH=../api:. python -m pytest -q
```

Web (from `apps/web`): `npm run lint`, `npm run typecheck`, `npm run build` (install deps separately if needed).

### 8. Smoke test (local API must be running)

From repo root (set `BASE_URL` to your running API, e.g. `http://127.0.0.1:8000`):

```bash
source apps/api/.venv/bin/activate
export BASE_URL=http://127.0.0.1:8000
export SMOKE_INTERNAL_KEY=replace_me
export SMOKE_ORG_ID=org_dev_demo
export SMOKE_MEDIA_ASSET_ID=ma_dev_demo
python3 scripts/smoke_staging.py
```

Unset `SMOKE_INTERNAL_KEY` to run only public checks (`/health`, `/ready`, `/docs`, `/openapi.json`, manifest probe).

### 9. Example curl (Bearer + org headers)

Use the same `FF_INTERNAL_API_KEY` value as the Bearer token, and the seeded org id `org_dev_demo`.

```bash
export API_KEY=replace_me
export H="Authorization: Bearer $API_KEY"
export O="X-Org-Id: org_dev_demo"

# Account (canonical processing-minute balance + annual access)
curl -sS "http://localhost:8000/v1/account" -H "$H" -H "$O"
curl -sS "http://localhost:8000/v1/account/usage" -H "$H" -H "$O"
# Deprecated compatibility alias only — same JSON as /v1/account; do not use “credits” in product copy
curl -sS "http://localhost:8000/v1/account/credits" -H "$H" -H "$O"

# Output kinds catalog
curl -sS "http://localhost:8000/v1/catalog/outputs" -H "$H" -H "$O"

# Presign upload (requires active annual access on the org)
curl -sS -X POST "http://localhost:8000/v1/uploads/presign" \
  -H "$H" -H "$O" -H "Content-Type: application/json" \
  -d '{"filename":"clip.mp4","content_type":"video/mp4","file_size_bytes":1048576,"media_type":"video"}'

# After browser/client PUT to upload_url — confirm object landed
curl -sS -X POST "http://localhost:8000/v1/uploads/complete" \
  -H "$H" -H "$O" -H "Content-Type: application/json" \
  -d '{"media_asset_id":"ma_..."}'

# Create job (use media_asset_id; minimum outputs for a small estimate)
curl -sS -X POST "http://localhost:8000/v1/jobs" \
  -H "$H" -H "$O" -H "Content-Type: application/json" \
  -d '{"media_asset_id":"ma_...","requested_outputs":["transcript"]}'

# List jobs (paging + optional status filter)
curl -sS "http://localhost:8000/v1/jobs?status=queued&limit=50&offset=0" -H "$H" -H "$O"

# Job status
curl -sS "http://localhost:8000/v1/jobs/job_..." -H "$H" -H "$O"

# Cancel (releases reserved processing minutes when eligible)
curl -sS -X POST "http://localhost:8000/v1/jobs/job_.../cancel" -H "$H" -H "$O"

# Outputs (signed download URLs) + per-job doctrine catalog
curl -sS "http://localhost:8000/v1/jobs/job_.../outputs" -H "$H" -H "$O"
curl -sS "http://localhost:8000/v1/jobs/job_.../outputs/catalog" -H "$H" -H "$O"

# Public manifest (unauthenticated)
curl -sS "http://localhost:8000/v1/manifests/demo-creator/episode-001.json"
```

**Errors (canonical flat body on 4xx/5xx):**

```json
{"code": "machine_readable_code", "message": "Human-readable message.", "fields": []}
```

**Object key layout (R2):**

- Source uploads: `orgs/{org_id}/assets/{asset_id}/source/{filename}`
- Job outputs: `orgs/{org_id}/jobs/{job_id}/outputs/{name}.json` (e.g. `transcript.json`, `chapters.json`, `factsheet.json`, `faq.json`, `metadata.json`, `hosted_manifest.json`)
- Job manifest index: `orgs/{org_id}/jobs/{job_id}/manifest.json`

## Observability (Railway / load balancers)

- **`GET /health`** — liveness only (no database); use for Railway health checks.
- **`GET /ready`** — database connectivity plus strict-tier checks (R2/Stripe presence); returns **`503`** when `ready` is false.
- **`GET /version`** — app name, `APP_ENV`, `API_VERSION`, optional `GIT_COMMIT` / `BUILD_TIMESTAMP`.

Legacy **`GET /v1/health`** remains for older configs.

## OpenAPI

- Interactive docs: `http://localhost:8000/docs`
- Machine-readable: `http://localhost:8000/openapi.json`

## Railway (staging)

1. **Push this repo to GitHub** (see [docs/deployment-railway.md](docs/deployment-railway.md) — *Connect GitHub*). Suggested repo name: **`feedfoundry`**.
2. In Railway, point the **API** and **Worker** services at that repo with **root build context** and Dockerfiles **`apps/api/Dockerfile`** and **`apps/worker/Dockerfile`** respectively (not a bare `python:3.12-slim` image with no `COPY`). For the API, leave the **custom start command empty** (use Dockerfile `CMD`) or use `sh -c 'uvicorn … --port ${PORT:-8000}'` so `PORT` is not passed through as a literal `$PORT`.

Full checklist (GitHub, Dockerfile paths, `PORT`, public domain, env vars, redeploy order): **[docs/deployment-railway.md](docs/deployment-railway.md)**.

## Docker (from repo root)

```bash
docker build -f apps/api/Dockerfile -t feedfoundry-api .
docker build -f apps/worker/Dockerfile -t feedfoundry-worker .
```

## MCP

Configure the Railway MCP server in Cursor using `.cursor/mcp.json`. Review any infrastructure actions before applying them.

## Product doctrine

See `AGENTS.md` and `.cursor/rules/00-product-doctrine.mdc`. V1 does not ingest URLs; processing starts from uploaded files only.
