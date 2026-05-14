# Phase 7 — Railway, storage, and provider agnosticism

## Railway is baseline, not captivity

- **MVP deployment:** Railway for `apps/web`, `apps/api`, `apps/worker`, Postgres, and **external** S3-compatible object storage.
- **Product logic** must not hard-code Railway private URLs or assume Railway-only volumes for large blobs.
- **Containers** should remain portable (Dockerfile patterns, 12-factor env).

---

## Service boundaries

| Service | Responsibility |
|---------|----------------|
| **Web** (`apps/web`) | UI, BFF/proxy to API; **no AI provider keys** |
| **API** (`apps/api`) | Jobs, orgs, outputs metadata, auth, **no direct provider calls** for AI (keys live on worker) |
| **Worker** (`apps/worker`) | Job processing, **AI provider calls**, artifact writes |
| **Postgres** | Source of truth for rows; **not** for large media blobs |
| **Object storage** | S3-compatible: source media, intermediates, outputs, manifests, AI artifacts, signed URLs |

Optional **queue** later if DB polling is insufficient — not required for Phase 7 v1 design lock-in.

---

## Storage architecture requirements

- **Storage provider abstraction** (extend or formalise existing patterns): local dev mock, S3-compatible prod.
- **Artifact path conventions** — documented, no customer secrets in paths, no public objects without signed URL / policy.
- **Artifacts include:** transcript, factsheet, FAQ, chapters, metadata, CTAs, Hosted Manifest, visual reports, product reports/manifests, **AI run logs** (where stored — DB row + optional object for large payloads).

---

## Environment variables (document only — placeholder values in `.env.example`)

### AI / provider (worker)

- `OPENAI_API_KEY` — **server only**, worker (placeholder in repo)
- `AI_PROVIDER`, `AI_MODEL`, `AI_FALLBACK_PROVIDER`, `AI_FALLBACK_MODEL`
- `AI_MAX_JOB_COST`, `AI_MAX_ORG_DAILY_COST`, `AI_MAX_CONCURRENCY`
- `AI_TIMEOUT_SECONDS`, `AI_RETRY_LIMIT`
- `AI_ENABLE_MOCK_PROVIDER`
- `AI_STRUCTURED_OUTPUTS_ENABLED`, `AI_VISUAL_ANALYSIS_ENABLED`, `AI_REPOSITORY_BEACON_ENABLED`, `AI_PRODUCT_GRID_ENABLED`
- `AI_STORE_RUN_LOGS`, `AI_LOG_LEVEL` (optional)

### Storage

- `STORAGE_PROVIDER` (e.g. `s3`, `r2`, `local`)
- `STORAGE_BUCKET`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`
- `STORAGE_PUBLIC_BASE_URL` — only if architecture uses public CDN; **prefer signed URLs** for customer-facing fetch

### Railway operational (names are examples — document, don’t hardcode in code)

- Documented services: **api-v2-IQho**, **worker-v2** (per org runbook); avoid mutating legacy services from automation.

---

## Provider agnosticism

- **Interface:** `AIProvider.complete(request) -> response` (see AI Operating Brief).
- **Routing table:** per-stage primary + fallback models; config-driven.
- **Mock provider** in CI/dev without network.
- **No browser keys**; **no** hard dependency on OpenAI SDK types leaking across API boundary.

---

## Deployment assumptions (docs only)

- Migrations run against staging/prod Postgres per existing process — not automated in this doc.
- Worker receives same `DATABASE_URL` pattern as today; AI keys only on worker service.
- **No** deployment commands executed from Captain automation without Steve naming the service.

---

## Portability checklist (for implementers)

- [ ] No Railway hostname strings in `apps/api` / `apps/worker` business logic  
- [ ] Storage access only via adapter  
- [ ] AI only via adapter module in worker  
- [ ] Feature flags for visual / product / beacon  
- [ ] `.env.example` lists all vars with `replace_me` / empty safe placeholders  
