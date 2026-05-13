# Railway deployment (FeedFoundry)

This document describes a **staging-oriented** Railway layout: API, worker, and Postgres. The commercial model remains **annual hosted archive access** plus **processing credits** (not monthly subscription SaaS).

## Connect GitHub so Railway builds this monorepo (not a bare image)

If your API or worker service only shows **`python:3.12-slim`** (or “empty” deploy) with **no `COPY` of this repo**, Railway is **not** building from your application source. Fix it as follows for **each** HTTP service (API) and **each** worker service.

### Recovery: “GitHub Repo not found”, Source Image, or npm commands

If the API service shows **GitHub Repo not found**, **`Source Image: python:3.12-slim`**, **Pre-deploy: `npm run migrate`**, or **Start: `npm run start`**, the service is still wired like a **Node template**, not this repo.

Do this **in order**:

1. **GitHub access for Railway**  
   - On **GitHub**: **Settings → Applications → Installed GitHub Apps** (or **OAuth Apps**) → **Railway** → **Configure**.  
   - Under **Repository access**, ensure **`stevensonindustriesholdings-sudo/feedfoundry`** is allowed (or “All repositories” for a quick fix).  
   - Save. If the repo was private or newly created, **re-authorize** so Railway can list it.

2. **Disconnect the wrong deploy path**  
   - In the **API** service on Railway: find **Source** / **Deploy** settings.  
   - **Remove** or **disconnect** any **Source Image** / **Docker Hub image** / standalone **`python:3.12-slim`** deploy so the service is **not** image-only.  
   - The live app must come from **GitHub → Dockerfile build**, not a placeholder base image.

3. **Attach GitHub + Dockerfile (API)**  

   | Field | Value |
   |--------|--------|
   | Source | **GitHub** → `stevensonindustriesholdings-sudo` / **`feedfoundry`** |
   | Branch | **`main`** |
   | Root directory | **`.`** or blank (monorepo root) |
   | Builder | **Dockerfile** |
   | Dockerfile path | **`apps/api/Dockerfile`** |

4. **Clear Node/npm leftovers**  
   - **Pre-deploy command:** **empty** (remove `npm run migrate`). Migrations for this stack are **`alembic`**, run manually or in a separate job — not npm.  
   - **Custom Start Command:** **empty** (remove `npm run start`). The API image **`CMD`** runs Uvicorn (see `apps/api/Dockerfile`).

5. **Networking (API only)**  
   - **Public domain:** enabled.  
   - **Health check path:** **`/health`**.  
   - **Target / internal port:** Railway sets **`PORT`** in the container; the Dockerfile listens on **`${PORT:-8000}`**. If the UI asks for a **target port**, use **`8000`** unless Railway docs for your layout say otherwise (the process must match the port the proxy forwards to).

6. **Redeploy API only**  
   - Trigger a **new deployment** on the API service and open **Build logs**. You should see Docker **`COPY`** lines for `ai-routing.yaml` and `apps/api/...`. If you only see a bare slim image pull with no repo `COPY`, the GitHub Dockerfile build is still not active.

7. **Worker**  
   - Leave the worker service **unchanged** until **`GET /health`** on the API returns **200** with JSON. Then configure the worker with the **same** GitHub repo, root **`.`**, Dockerfile **`apps/worker/Dockerfile`**, no source image, blank pre-deploy and start command, **no** public domain.

### 1. Push this repository to GitHub

Create an empty GitHub repository (suggested name: **`feedfoundry`**), then from your machine (repo root):

```bash
git remote add origin git@github.com:<your-username>/feedfoundry.git
git branch -M main
git push -u origin main
```

Use HTTPS if you prefer: `https://github.com/<your-username>/feedfoundry.git`.

### 2. API service — source and Docker

In the Railway project: open the **API** service → **Settings** (or **Source**).

| Setting | Value |
|--------|--------|
| **Source** | Connect **GitHub**, pick the `feedfoundry` repo and branch (e.g. `main`). |
| **Root directory** | Leave **empty** or `.` — build context must be the **monorepo root** so `COPY apps/...` and `COPY ai-routing.yaml` in the Dockerfile resolve. |
| **Builder** | **Dockerfile** (not Nixpacks-only, not “empty” image). |
| **Dockerfile path** | `apps/api/Dockerfile` |

**Start command:** leave **blank** so the image **`CMD`** runs (recommended). The API Dockerfile uses **shell form** so `PORT` expands:

```text
sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
```

**Do not** set a bare `uvicorn … --port $PORT` (or `--port $PORT`) as the Railway start command without a shell — Uvicorn will treat `$PORT` as a literal string and crash. If you must override the start command, use:

`sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'`

**Public networking:** enable **Generate domain** (or attach your custom domain) on the **API** service so `/health`, `/docs`, and webhooks are reachable.

**Health check path:** `GET /health` (see `infra/railway/railway.json` for a reference template).

**Liveness vs readiness:** Railway’s health probe should hit **`/health`** (no DB). With **`APP_ENV=staging`**, the API process boots once **`DATABASE_URL`** and a non-placeholder **`FF_INTERNAL_API_KEY`** are set; missing R2/Stripe/PUBLIC URL surfaces as **`GET /ready`** returning **`503`** with details, not as a crash before bind. With **`APP_ENV=production`** (or **`prod`**), startup still **fails fast** if R2, Stripe, or HTTPS public URL is invalid — fix env or use **`staging`** until the stack is fully wired.

**`PORT`:** Do **not** set a manual **`PORT`** variable in Railway unless you intend to override the platform-injected listen port. Leave **Custom Start Command** empty so the Dockerfile **`CMD`** runs (`sh -c '…${PORT:-8000}…'`). If the service **Networking → Target port** exists, align it with the port the process listens on (Railway’s injected **`PORT`**, or **8000** when unset locally).

**Health check timeout:** If builds succeed but the first deploy is slow (cold start), raise the health check timeout (e.g. **30 → 120** seconds) temporarily, redeploy API only, then tune back down.

### 3. Worker service — same repo, different Dockerfile

Open the **Worker** service → same GitHub repo and branch.

| Setting | Value |
|--------|--------|
| **Root directory** | Empty or `.` (monorepo root). |
| **Dockerfile path** | `apps/worker/Dockerfile` |

**Start command:** leave **blank** (image `CMD` is `python worker.py`). The worker **does not** need a public port or HTTP health check.

### 4. Redis (optional for current code)

The FeedFoundry API and worker **do not read `REDIS_URL` or any Redis client** in the current codebase (Postgres + R2 + Stripe only). A Railway **Redis** plugin is fine to keep for future use, but you **do not** need to attach Redis variables to API/worker for the app to boot today.

### 5. Redeploy order

1. **API** — confirm build logs show `COPY` steps from this repo and the container listens on `PORT`.  
2. **Worker** — deploy after API image pattern is correct (same repo, worker Dockerfile).

### 6. Smoke checks after deploy

From your laptop (no secrets in output):

```bash
export BASE_URL=https://<your-api-public-host>
curl -sS "$BASE_URL/health" | head -c 400
curl -sS "$BASE_URL/ready" | head -c 800
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE_URL/openapi.json"
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE_URL/docs"
```

Or run `python3 scripts/smoke_staging.py` with `BASE_URL` set (see [Smoke test](#smoke-test-staging) below).

---

## Required Railway services

| Service | Role |
|--------|------|
| **Postgres** | Primary database for API and worker |
| **API** | FastAPI (`uvicorn`), HTTP only; health checks use **`GET /health`** (liveness, no DB) |
| **Worker** | Long-running Python process; **no HTTP port**; polls Postgres for jobs |

Build both Docker images **from the monorepo root** (API installs **`apps/api/requirements.txt`**, aligned with `pyproject.toml`):

```bash
docker build -f apps/api/Dockerfile -t feedfoundry-api .
docker build -f apps/worker/Dockerfile -t feedfoundry-worker .
```

The API container runs Uvicorn on **`${PORT:-8000}`** (Railway sets `PORT`).

## Environment variables

Copy [`.env.example`](../.env.example) as a checklist. At minimum for **staging/production**:

- **Database**: `DATABASE_URL` — copy or **reference** the connection string from your Railway **Postgres** service into both **API** and **Worker** (identical value).
- **App**: `APP_ENV=staging` (or `production`), `PUBLIC_API_BASE_URL` (HTTPS URL of this API service; required in strict tiers)
- **Internal auth**: `FF_INTERNAL_API_KEY` (non-placeholder in strict tiers)
- **R2**: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_SOURCE`, `R2_BUCKET_OUTPUTS`
- **Stripe**: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (and price IDs per your Stripe products)

Optional but recommended:

- `GIT_COMMIT`, `BUILD_TIMESTAMP` — shown on `GET /version`
- **Worker**: `WORKER_POLL_INTERVAL_SECONDS`, `FF_WORKER_ID` (stable id per replica), same `DATABASE_URL` / R2 / `APP_ENV` as API

### Staging services `api-v2-IQho` and `worker-v2` only

Do **not** apply the following to legacy API/worker Railway services.

| Variable | Service | Notes |
|----------|---------|--------|
| `FF_STRICT_SOURCE_VERIFY` | **`worker-v2` only** | Set to `1` **after** you have proven the real upload path (presign → PUT → job completes). When `1`, a missing source object fails the job with `source_object_missing` even in `APP_ENV=staging`. Redeploy **`worker-v2`** after changing this variable. |
| `FFPROBE_BINARY` | **`worker-v2`** (optional) | Defaults to `ffprobe` on `PATH` (installed with `ffmpeg` in `apps/worker/Dockerfile`). |

End-to-end upload smoke and output expectations: [real-media-verification-sprint.md](real-media-verification-sprint.md).

The API **fails fast on startup** in `staging` / `production` / `prod` if critical variables are missing or placeholders (see `app.config.env_validation`).

## API start command

From the API image (working directory and `PYTHONPATH` are set in `apps/api/Dockerfile`), the process must run **under a shell** so Railway’s `PORT` expands:

```bash
sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
```

The Dockerfile **`CMD`** uses that pattern. Do not use Docker **exec-form** `CMD ["uvicorn", …, "--port", "$PORT"]` — variables are not expanded.

Railway’s `infra/railway/railway.json` `startCommand` uses the same `sh -c` wrapper if you copy it into the dashboard.

## Worker start command

From the worker image (see `apps/worker/Dockerfile`):

```bash
python worker.py
```

Ensure `PYTHONPATH` includes `apps/api` so `app.*` imports resolve (the repo Dockerfile should mirror local `PYTHONPATH=../api:.`).

## Migrations

Migrations live under `apps/api/alembic/`. **Run manually** (or in a one-off deploy job) against the same `DATABASE_URL` as production:

```bash
cd apps/api
PYTHONPATH=. alembic -c alembic.ini upgrade head
```

They are **not** automatically run by the API server on boot (keeps rollouts predictable). Typical options:

1. **Railway one-off shell** or **release phase** running `alembic upgrade head` before the new revision serves traffic, or  
2. A dedicated **migration** service/job triggered on deploy.

## Seed script

```bash
export DATABASE_URL=postgresql+psycopg://…
PYTHONPATH=apps/api python scripts/seed_dev.py
```

**Warning:** `scripts/seed_dev.py` **refuses to run** when `APP_ENV` is `production` or `prod` **unless** `ALLOW_DEV_SEED=true` is set. Do **not** set `ALLOW_DEV_SEED` in real production unless you explicitly intend to insert demo orgs and grants into prod.

Use seed only on **staging** or local dev with a disposable database.

## Stripe (test mode) webhooks

1. In Stripe Dashboard (test mode), create a webhook endpoint pointing to:  
   `https://<your-api-host>/v1/stripe/webhook`
2. Copy the **signing secret** into `STRIPE_WEBHOOK_SECRET`.
3. Set `STRIPE_SECRET_KEY` to your test secret key.
4. Map Checkout **Price IDs** to FeedFoundry using the `STRIPE_ANNUAL_*` and `STRIPE_CREDIT_PACK_*` variables (see `.env.example`).

## Cloudflare R2

1. Create R2 buckets for source and outputs; note account id, access key id, and secret.
2. Set `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_SOURCE`, `R2_BUCKET_OUTPUTS`.
3. Optional: `R2_PUBLIC_BASE_URL` if you serve public reads via a custom domain.

The API builds the S3 endpoint as `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` (see `app.settings.r2_s3_endpoint_url`). Readiness checks **config presence only** — no object I/O on `/ready`.

## Post-deploy checks

After the API is live:

| Check | Expected |
|--------|----------|
| `GET /health` | `200`, JSON `status: ok` (no DB) |
| `GET /ready` | `200` if fully ready, **`503`** if `ready: false` (e.g. DB down); JSON includes `checks` |
| `GET /version` | `200`, app name, env, optional git/build fields |
| `GET /docs` | Swagger UI |
| `GET /openapi.json` | OpenAPI schema |

Example:

```bash
curl -sS "https://<host>/health" | jq .
curl -sS "https://<host>/ready" | jq .
```

Repo `infra/railway/railway.json` uses **`healthcheckPath`: `/health`**.

## Smoke test (staging)

From repo root, with the API URL and optional internal key:

```bash
export BASE_URL=https://your-staging-api.up.railway.app
export SMOKE_INTERNAL_KEY=<same value as FF_INTERNAL_API_KEY>
export SMOKE_ORG_ID=org_dev_demo
# Optional, after seed:
export SMOKE_MEDIA_ASSET_ID=ma_dev_demo

python3 scripts/smoke_staging.py
```

The script exits non-zero on failure and skips authenticated / job steps when variables are unset.

## Railway MCP

If you use Cursor’s Railway MCP (`.cursor/mcp.json`), review any proposed infrastructure changes before applying them.
