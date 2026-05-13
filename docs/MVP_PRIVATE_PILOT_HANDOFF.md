# FeedFoundry MVP private pilot — build captain handoff

**Integration branch:** `mvp/private-pilot-v01`  
**Preserved WIP snapshot:** `wip/local-state-before-mvp-integration` (commit `5f88432`)  
**Contract on `main`:** `642fee5` (`docs/MVP_PARALLEL_CONTRACT.md`, `.cursor/rules/feedfoundry-mvp.mdc`)

Parallel agent worktrees (`agent/auth-account-ownership` … `agent/railway-ai-controls`) were still at the contract commit; **all substantive MVP code** came from the preserved dirty tree on `main` plus this captain pass (billing routes, `ACCESS_INACTIVE`, `MEDIA_DURATION_TOO_LONG`, customer copy, tests).

---

## What shipped on `mvp/private-pilot-v01`

| Area | Summary |
|------|---------|
| **Access** | Uploads and jobs require active annual access. **403** returns `{"error":"ACCESS_INACTIVE",...}` (replaces plain `annual_access_required` string). |
| **Processing time** | Wallet units = **minutes**. Goodwill shortfall ≤ `FF_GOODWILL_MAX_SHORTFALL_MINUTES` (default 5). Block payload uses **INSUFFICIENT_PROCESSING_TIME** and contract-style copy. |
| **Media cap** | Jobs rejected when `media.duration_seconds > FF_MAX_MEDIA_SECONDS` (default 7200) with **MEDIA_DURATION_TOO_LONG**. |
| **Stripe** | **MVP price IDs:** `STRIPE_ANNUAL_ACCESS_PRICE_ID` → annual row `plan_code=annual_access` + grant included minutes; `STRIPE_PROCESSING_TIME_PRICE_ID` → `purchase_credits_from_stripe` with memo `processing_time_topup`. Legacy core/lite/studio + credit-pack IDs unchanged. |
| **Billing HTTP** | `POST /v1/billing/checkout/access`, `POST /v1/billing/checkout/processing-time`, `POST /v1/billing/webhook` (alias of existing webhook handler). |
| **Worker** | **`FF_AI_ENABLED=false`** forces empty OpenAI key → transcript stub path (no provider calls). |
| **Web** | Pricing / home / layout / upload copy use **processing time** language; dashboard proxy title avoids exposing “credits”; `mapUpstreamError` handles JSON `detail` and maps **ACCESS_INACTIVE** / insufficient time. |
| **Tests** | Account isolation; billing 503s; billing webhook alias; MVP Stripe price; media-too-long; **48** API tests passing (excluding `test_production_deps_import` which needs full native drivers in this sandbox). |

---

## Migrations

- Existing: `apps/api/alembic/versions/006_job_goodwill_and_credit_enum.py` (from WIP branch — apply on Postgres before relying on goodwill columns / enums).

---

## Environment variables (Railway / local)

**Required for billing Checkout**

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | Stripe API |
| `STRIPE_WEBHOOK_SECRET` | Webhook signature |
| `STRIPE_ANNUAL_ACCESS_PRICE_ID` | MVP annual Checkout line item |
| `STRIPE_PROCESSING_TIME_PRICE_ID` | MVP top-up Checkout line item |
| `APP_BASE_URL` | Success/cancel URLs (fallback: `PUBLIC_API_BASE_URL`) |

**Optional / defaults**

| Variable | Default | Purpose |
|----------|---------|---------|
| `STRIPE_ANNUAL_ACCESS_INCLUDED_MINUTES` | 300 | Granted with MVP annual SKU |
| `STRIPE_PROCESSING_TIME_PACK_MINUTES` | 600 | Minutes for MVP top-up SKU |
| `FF_GOODWILL_MAX_SHORTFALL_MINUTES` | 5 | Goodwill shortfall cap |
| `FF_GOODWILL_MAX_MINUTES_PER_ACCOUNT_PER_YEAR` | 30 | Annual goodwill cap (ledger) |
| `FF_MAX_MEDIA_SECONDS` | 7200 | Job creation guard |
| `FF_AI_ENABLED` | true | Worker: disable OpenAI path when false |
| `FF_DEFAULT_MODEL`, `FF_MODEL_*` | see `settings.py` | Reserved for future per-stage models |
| `FF_MAX_TOKENS_PER_JOB`, `FF_MAX_COST_PER_JOB_GBP`, `FF_RETRY_MAX` | caps | Documented; deeper enforcement TODO in worker |

**Unchanged:** R2, `FF_INTERNAL_API_KEY`, database URL, legacy Stripe price IDs for core/lite/studio and credit packs.

---

## HTTP endpoints (customer-relevant)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/v1/uploads/presign` | Requires active access |
| POST | `/v1/jobs` | Access + duration + processing-time reserve / goodwill |
| GET | `/v1/jobs/{id}` | Org-scoped |
| GET | `/v1/jobs/{id}/outputs` | Org-scoped |
| GET | `/v1/account/credits` | **Legacy path** — response includes `processing_minutes_*` (+ legacy `credits_*` mirrors for compatibility) |
| POST | `/v1/billing/checkout/access` | Stripe Checkout session (annual MVP SKU) |
| POST | `/v1/billing/checkout/processing-time` | Stripe Checkout session (top-up MVP SKU) |
| POST | `/v1/billing/webhook` | Same as `/v1/stripe/webhook` |
| POST | `/v1/stripe/webhook` | Unchanged |

---

## Commands run (captain)

```bash
# From repo root; API tests (venv must have apps/api/requirements.txt installed)
cd apps/api && PYTHONPATH=. ../../.venv/bin/python -m pytest tests/ -q --ignore=tests/test_production_deps_import.py

# Customer copy guard
PYTHONPATH=. ../../.venv/bin/python -m pytest tests/test_customer_copy_no_credits.py -q
```

---

## Tests: passed / skipped

- **Passed:** 48 API tests (`--ignore=tests/test_production_deps_import.py`).
- **Not run in CI here:** `test_production_deps_import` (psycopg “pq wrapper” / full driver stack on this host).

---

## Remaining blockers / TODO

1. **Rename internal “credits” API fields** — `estimated_credits` / `reserved_credits` on job payloads remain for backward compatibility; UI should prefer `estimated_minutes` / processing fields.
2. **Worker AI caps** — `FF_MAX_TOKENS_PER_JOB`, cost GBP caps, and structured **AIUsageLog** on every OpenAI call are only partially enforced (transcript path respects `FF_AI_ENABLED`).
3. **Admin retry/cancel** — confirm admin routes match product copy (“processing minutes” only in UI).
4. **Stripe Dashboard** — configure product metadata as in `docs/MVP_PARALLEL_CONTRACT.md` for your own auditing; price-ID mapping is the source of truth in code today.
5. **Production pytest** — run full suite including `test_production_deps_import` on Railway-like Linux with Postgres drivers.

---

## Railway

- Deploy **API** and **worker** from `mvp/private-pilot-v01` after migrations.
- Set new env vars in Railway service settings (see table above).
- Worker must receive **`FF_AI_ENABLED`** and **`OPENAI_API_KEY`** if Whisper is desired.

---

## Stripe test mode

1. Create two Prices: **annual access** and **processing time top-up**; set IDs in `STRIPE_ANNUAL_ACCESS_PRICE_ID` / `STRIPE_PROCESSING_TIME_PRICE_ID`.
2. Point webhook to `https://<api>/v1/billing/webhook` or `/v1/stripe/webhook`.
3. Use **Stripe CLI:** `stripe listen --forward-to localhost:8000/v1/billing/webhook` for local runs.
4. Complete Checkout with session metadata containing `ff_organisation_id` (API sets this automatically).

---

## Private pilot launch checklist

- [ ] Run Alembic through head on staging Postgres.
- [ ] Set Stripe + `APP_BASE_URL` + R2 + internal API key on API service.
- [ ] Set same processing/AI env vars on **worker**.
- [ ] Smoke: presign → PUT → job → 7 outputs (existing `tools/smoke_real_media_upload.py`).
- [ ] Confirm dashboard shows **processing time** and no forbidden words on pilot-facing pages (`test_customer_copy_no_credits` paths).
- [ ] One real Checkout for annual + one for top-up; verify wallet minutes and `annual_access` row.
- [ ] Negative: org **B** cannot open org **A** job URL (`test_account_isolation`).

---

## Git branches pushed (this session)

- `wip/local-state-before-mvp-integration`
- `mvp/private-pilot-v01`
- `agent/auth-account-ownership` (was missing on remote; now pushed)

`main` remains clean at **`origin/main` = `642fee5`** until you merge the MVP branch.
