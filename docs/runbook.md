# FeedFoundry setup and operations runbook

Single entry point for engineers and operators: what the product is, how to run it locally, where secrets live, how AI and billing are wired, and how Railway/Base44 fit together.

---

## 1. What FeedFoundry is

FeedFoundry is a **creator archive intelligence engine**. Creators **upload** their own media files (video, audio, podcast-style assets). The system runs **FFmpeg** and **AI-assisted** pipelines on a **worker**, persists state in **Postgres**, stores blobs in **R2 (or S3-compatible) object storage**, and exposes a **FastAPI** service with **OpenAPI** for clients.

**V1 constraint:** there is **no URL ingestion**. Every job starts from an uploaded object in your bucket, not from an arbitrary external link.

**Current `/v1` surface (integrators):** `GET /v1/account`, `GET /v1/account/usage`, `GET /v1/account/credits` (deprecated compatibility alias only), `GET /v1/catalog/outputs`, `POST /v1/uploads/presign`, `POST /v1/uploads/complete`, `POST /v1/jobs`, `GET /v1/jobs` (query `status`, `limit`, `offset`), `GET /v1/jobs/{job_id}`, `POST /v1/jobs/{job_id}/cancel`, `GET /v1/jobs/{job_id}/outputs`, `GET /v1/jobs/{job_id}/outputs/catalog`, plus existing manifest routes under `/v1/manifests/...`. Errors: flat JSON `{"code","message","fields"}`.

This monorepo is the **engine** (API + worker + schemas + prompts). A separate product layer (e.g. **Base44**) owns polished customer UI, auth, and payment UX; it calls this API with server-side credentials.

---

## 2. Product model (customer-facing language)

- **Annual hosted archive access:** the creator pays for a **year** of entitlement to the hosted archive, manifests, and related surfaces—not “monthly SaaS tiers.”
- **Processing allowance:** metered in **processing minutes** / **processing hours** (whole minutes on the internal ledger; display helpers may show hours). For customer copy, describe **included processing minutes** with the annual plan, plus optional **processing add-on packs**—not as abstract “AI credits” or gamified currency.

Plans also enforce **limits per job** (e.g. max media minutes, max file size, concurrent jobs); see `ai-routing.yaml` under `plans:`.

---

## 3. Internal ledger vs public wording

The codebase and database retain **historical identifiers** (`credit_wallets`, `credit_transactions`, Stripe env names like `STRIPE_*_CREDITS`, YAML `fail_closed_on_missing_credit_reservation`) — values are **processing minutes** in the integrated engine. **Public documentation, marketing, and Base44 UI copy** should use **processing allowance**, **processing minutes** / **processing hours**, and **processing add-ons**—not **“credits”** as the customer-facing model. Where the HTTP path **`/v1/account/credits`** or JSON **`*_credits`** appears, treat it as **deprecated compatibility alias** only (mirror of canonical **`*_processing_minutes`** fields).

---

## 4. Failed, cancelled, and completed jobs vs processing allowance

Jobs follow **reserve → settle** on the internal ledger (whole **processing minutes**):

- Before heavy work, the API **reserves** estimated minutes against **`processing_minutes_available`**.
- On **successful completion**, the worker **`_settle_processing_allowance`** charges **`actual_processing_minutes_charged`** (up to the reservation) and **releases** any unused remainder via **`ledger_release_remainder_key`**.
- On **failure**, the worker **releases the full reservation** via **`ledger_release_failure_key`** — **failed jobs do not consume** allowance as completed usage (**`actual_processing_minutes_charged`** stays unset for that outcome).
- On **cancellation** (`POST /v1/jobs/{job_id}/cancel`), the API releases reserved minutes for eligible states — **cancelled jobs do not consume** completed processing allowance the way **completed** jobs do.

**Invariant:** only **completed** jobs settle **actual processing minutes charged** toward the creator’s allowance. **Failed** and **cancelled** do not.

---

## 5. Local setup (high level)

Repository root: use one Python virtualenv for API + worker imports, Postgres, and (for full path) R2 or dev flags.

1. **Python venv** — from repo root:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -r apps/api/requirements.txt pytest ruff
   pip install -r apps/worker/requirements.txt
   ```

2. **Environment** — `cp .env.example .env.local` and fill required variables (see below). The API reads settings from the environment; align variable names with [`.env.example`](../.env.example).

3. **Database migrations** — from `apps/api` with `PYTHONPATH=.`:

   ```bash
   export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/feedfoundry
   cd apps/api && PYTHONPATH=. alembic -c alembic.ini upgrade head && cd ../..
   ```

4. **Seed dev org (optional)** — `PYTHONPATH=apps/api python scripts/seed_dev.py` with the same `DATABASE_URL`. See README for guards (`ALLOW_DEV_SEED` in production).

5. **Node (web only)** — `cd apps/web && npm install && cp .env.example .env.local`.

Detailed curl examples and R2 key layout: [README.md](../README.md).

---

## 6. Required environment variables

Authoritative template with comments: **[`.env.example`](../.env.example)** (repo root). Summary:

| Area | Variables |
|------|-----------|
| App | `APP_ENV`, `APP_NAME`, `PUBLIC_API_BASE_URL`, `API_VERSION` |
| Database | `DATABASE_URL` |
| Internal auth | `FF_INTERNAL_API_KEY`, `BASE44_WEBHOOK_SECRET` (when webhooks used) |
| AI policy file | `AI_ROUTING_CONFIG_PATH` (optional; default path in Docker) |
| Storage | `STORAGE_PROVIDER`, `R2_*` or `R2_ENDPOINT_URL`, buckets, optional `R2_PUBLIC_BASE_URL`, presign TTLs |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, annual price IDs, plan codes, **internal** included-unit envs, processing add-on pack price IDs |
| Providers | `OPENAI_API_KEY`, model envs; optional `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY`, local/OSS model envs |
| AI budgets | `DEV_MONTHLY_AI_BUDGET_USD`, `STAGING_MONTHLY_AI_BUDGET_USD`, `PRODUCTION_MONTHLY_AI_BUDGET_USD`, throttle/stop percents |
| Worker | `WORKER_POLL_INTERVAL_SECONDS`, `FF_WORKER_ID`, `MAX_CONCURRENT_JOBS_PER_WORKER`, `FFMPEG_BINARY`, `FFPROBE_BINARY`, `FF_SKIP_SOURCE_VERIFY` |

Strict tiers (`staging` / `production` / `prod`) **fail fast** on missing or placeholder critical values; see `apps/api/app/config/env_validation.py`.

---

## 7. Where secrets go

- **Never** commit secrets. Use **`.env.local`** (gitignored) or your host’s secret store.
- **Railway:** set secrets as **service variables** on the API and worker services (same `DATABASE_URL` and storage keys where applicable).
- **Browser:** **no** API keys, Stripe secrets, or `FF_INTERNAL_API_KEY`. The Next.js app uses **server-only** `FEEDFOUNDRY_INTERNAL_API_KEY` and proxies via `apps/web/src/app/api/ff/[...path]/route.ts`.
- **CI:** inject via protected variables; do not print `DATABASE_URL` or keys in logs.

---

## 8. How to run the web app

From repo root:

```bash
cd apps/web
cp .env.example .env.local
# Set FEEDFOUNDRY_API_BASE_URL, FEEDFOUNDRY_INTERNAL_API_KEY (matches FF_INTERNAL_API_KEY on API), defaults
npm install
npm run dev
```

Open `http://localhost:3000`. Production-like serve: `npm run build && npm run start`.

See [apps/web/README.md](../apps/web/README.md) and [apps/web/.env.example](../apps/web/.env.example).

---

## 9. How to run the API (FastAPI)

From repo root with venv activated:

```bash
export DATABASE_URL=...
export FF_INTERNAL_API_KEY=replace_me
cd apps/api
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Docs: `http://localhost:8000/docs`
- Liveness: `GET /health` (no DB)
- Readiness: `GET /ready` (DB + strict checks)

Docker: `docker build -f apps/api/Dockerfile -t feedfoundry-api .` from monorepo root.

---

## 10. How to run the worker and FFmpeg pipeline

The worker is a **long-running poller** (no HTTP server). It needs the **same** `DATABASE_URL` and storage configuration as the API, plus `PYTHONPATH` including `apps/api` for shared models and ledger.

```bash
source .venv/bin/activate
export DATABASE_URL=...
# Same R2 (or S3) variables as API
export FF_SKIP_SOURCE_VERIFY=true   # local only, skips HEAD on source object
cd apps/worker
PYTHONPATH=../api:. python worker.py
```

Ensure **`ffmpeg`** and **`ffprobe`** are on `PATH` or set `FFMPEG_BINARY` / `FFPROBE_BINARY`.

Docker: `docker build -f apps/worker/Dockerfile -t feedfoundry-worker .`

---

## 11. How to run tests

```bash
cd apps/api && source .venv/bin/activate && python -m pytest -q
cd ../worker && PYTHONPATH=../api:. python -m pytest -q
```

Web: `cd apps/web && npm run lint`, `npm run typecheck`, `npm run build`. Optional API/worker lint: `ruff check apps/api/app apps/worker` if `ruff` is installed.

---

## 12. Railway deployment notes

Full checklist: **[deployment-railway.md](./deployment-railway.md)**.

**Assumptions:**

- Monorepo connected from **GitHub**; **root directory** `.` (repo root); **Dockerfile** builds (not a bare base image without `COPY`).
- **API service:** `apps/api/Dockerfile`, public domain, health check **`/health`**, start command either empty (image `CMD`) or `sh -c 'uvicorn … --port ${PORT:-8000}'` so `PORT` expands.
- **Worker service:** `apps/worker/Dockerfile`, no public port.
- **Postgres** attached; `DATABASE_URL` referenced on both services.
- **Migrations:** run `alembic upgrade head` manually or via release phase (not `npm`).

Team staging convention (see workspace automation rules): API **`api-v2-IQho`**, worker **`worker-v2`**. Treat other similarly named services as legacy unless explicitly in scope.

---

## 13. Base44 frontend handoff

- **Base44** implements landing, pricing, dashboard, uploads, job progress, outputs, wallet/annual access UI, and admin—using this API’s **OpenAPI** contract.
- **Engine responsibilities:** presigned uploads, job lifecycle, outputs, manifests, Stripe webhooks, ledger, AI routing policy file.
- **Security:** Base44 must **proxy** authenticated calls with **server-side** credentials; never expose `FF_INTERNAL_API_KEY` or Stripe secrets to the browser.
- Tone and UX notes: [base44-vibe-guide.md](./base44-vibe-guide.md).
- HTTP details and schemas: [api-contract.md](./api-contract.md).

---

## 14. AI provider and model routing

- **Policy file:** [`ai-routing.yaml`](../ai-routing.yaml) at repo root (copied into API/worker images). Defines per-**module** primary and **fallback** providers.
- **Baseline:** **OpenAI** for transcription and many text modules; **fallbacks** include **Google (Gemini)**, **Anthropic (Claude)**, **Groq**, **DeepSeek**, **Mistral**, and **local** JSON repair / transcription paths via env-configured models.
- **Model names** are read from **environment variables** referenced in YAML (`model_env`); not hardcoded in Python router builders (`apps/api/app/services/ai_router.py`).
- **Implementations:** `apps/worker/providers/` (`openai_provider`, `google_provider`, `anthropic_provider`, `groq_provider`, `deepseek_provider`, `mistral_provider`, `local_provider`, …).

---

## 15. Rate limits, retries, budgets, and fallbacks

From `ai-routing.yaml` `global` section (see file for current numbers):

- **Retries:** `default_max_retries`, exponential-style **`retry_backoff_initial_seconds`** → **`retry_backoff_max_seconds`**, optional **`retry_jitter`**.
- **Timeouts:** `default_timeout_seconds` per module overrides.
- **Concurrency:** `max_concurrent_ai_calls_per_worker`, org-level pending/running caps under `plans` / related settings.
- **Monthly USD ceilings:** env `DEV_MONTHLY_AI_BUDGET_USD`, `STAGING_MONTHLY_AI_BUDGET_USD`, `PRODUCTION_MONTHLY_AI_BUDGET_USD` with **soft alert**, **throttle**, and **hard stop** percentages (`AI_SOFT_ALERT_PERCENT`, etc.).
- **Fail-closed:** `fail_closed_on_missing_cost_estimate`, `fail_closed_on_missing_credit_reservation` (internal ledger reservation required for billed AI paths).
- **Per-call:** each routed request carries token ceilings, temperature, timeout, retries, **cost ceiling** (internal units), and **fallback provider/model**.

Policy summary: [ai-cost-controls.md](./ai-cost-controls.md).

---

## 16. Glossary and acronyms

Canonical short glossary: [glossary.md](./glossary.md). Common acronyms:

| Term | Meaning |
|------|--------|
| **API** | FastHTTP service (`apps/api`); org-scoped routes under `/v1/`. |
| **R2** | Cloudflare R2 or compatible S3 API for sources and outputs. |
| **FF** | FeedFoundry internal prefix on keys and headers (`FF_INTERNAL_API_KEY`, `ff:…` idempotency keys). |
| **Presign** | Time-limited signed URL for direct browser → object storage upload. |
| **Manifest** | Hosted JSON describing an episode/asset for humans and agents (`hosted_manifest`). |
| **Ledger** | Internal wallet: reserve / debit / release transactions (see section 3). |
| **YAML routing** | `ai-routing.yaml` module → provider/model/fallback/caps. |

---

## Related documents

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Quick start, curl examples, observability |
| [deployment-railway.md](./deployment-railway.md) | Railway dashboard recovery, env, smoke |
| [api-contract.md](./api-contract.md) | HTTP contract for integrators |
| [tech-spec.md](./tech-spec.md) | Component map and job states |
| [MVP_PARALLEL_CONTRACT.md](./MVP_PARALLEL_CONTRACT.md) | Multi-agent lane contract |
| [AGENTS.md](../AGENTS.md) | Repo-wide agent rules |

---

## Information that may still come from other workstreams

- **Exact Stripe Price IDs and live webhook signing secrets** for each environment (ops).
- **Final customer-facing copy** for annual plans and processing add-ons (product/Base44).
- **Production R2 public URL** strategy if manifests are served via CDN (infra).
- **Any migration from legacy Railway service names** to `api-v2-IQho` / `worker-v2` only if your project still has duplicates (ops).
