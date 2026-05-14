# Phase 7 — Internal AI run visibility (read-only)

Operators need a **safe, read-only** view of persisted **`AIRun`** / **`AIStageLog`** rows without exposing prompts, raw provider payloads, or secrets. This sprint adds HTTP surfaces and a minimal **System** page panel for staging.

## Authentication

All routes require the same **`FF_INTERNAL_API_KEY`** contract as other internal admin routes:

- `Authorization: Bearer <FF_INTERNAL_API_KEY>` (preferred), or
- `X-FF-Internal-Key: <FF_INTERNAL_API_KEY>` (legacy).

Missing or invalid credentials → **401** with flat JSON `{"code":"unauthorized","message":"…","fields":[]}`.

## Endpoints (FastAPI, under `/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/admin/ai-runs` | List recent runs. Query: `organisation_id` (optional), `job_id` (optional), `limit` (1–200, default 50). |
| `GET` | `/v1/admin/ai-runs/{ai_run_id}` | Detail one run with nested stages. |
| `GET` | `/v1/admin/jobs/{job_id}/ai-runs` | Runs for a job. Query: `organisation_id` (optional) — if present, job must belong to that org or **404** (`job_not_found`) to avoid cross-org leakage. |

## Redaction rules

Responses are **Pydantic-shaped** and intentionally omit:

- Raw **prompt** text (never stored on these visibility DTOs).
- **`extra_json`** on stages (may contain operational metadata unsuitable for broad operator paste-back).

Included fields are limited to identifiers, **status**, **provider/model names** as persisted on stages, timestamps, **validation_status**, structured **error_code** / **error_message**, token counts, **provider_request_id**, and **`cost_estimate_internal`** (documented as an internal rough estimate — **not** customer processing minutes or wallet balance).

**`provider_mode`** on the run envelope is **inferred** from distinct non-empty `provider_name` values on stages (`mixed` when they disagree).

## Web (Next.js)

The **`/system`** page (server-rendered) calls **`GET /v1/admin/ai-runs`** with the configured default organisation id. Optional URL filter: **`?job=<job_id>`**.

Copy avoids customer **“AI credits / tokens”** language; it references **mock provider** defaults and **canary disabled** unless worker env explicitly enables canary (see [phase7-openai-canary.md](./phase7-openai-canary.md)).

## Tests

`apps/api/tests/test_admin_ai_runs_visibility.py` covers auth, org scoping on the job-scoped route, list/detail shape, **`extra_json` / `prompt` absent** from JSON, and flat error bodies.

## Related

- Persistence model: `AIRun` / `AIStageLog` in `apps/api/app/models.py`.
- Worker pipeline context: [phase7-mock-ai-worker-pipeline.md](./phase7-mock-ai-worker-pipeline.md).
