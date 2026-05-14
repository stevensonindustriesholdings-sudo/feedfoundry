# Sprint report — 7C-12B (filled from `docs/REPORT_TEMPLATE.md`)

**Captain Autonomy Rules v1.5** — Sprint **7C-12B — Fix OpenAI 400 and rerun live canary**

---

## Sprint report

**Branch name:** `phase7/integration-7c1-ai-skeleton`  
**Commit hash:** `78c8f0d`

**Files changed:**

- `apps/worker/ai/schemas/output_contracts.py` — add `p7-canary-v1` / `1.0.0` strict-safe `P7CanaryFactsheetLivePayload` and registry entry
- `apps/worker/ai/canary_runner.py` — use P7 schema for HTTP request; validate with `FactsheetPayload` via `OutputValidator`
- `apps/worker/ai/mock_provider.py` — emit same stub shape for P7 key as factsheet
- `apps/worker/ai/openai_adapter.py` — redacted HTTP 400 diagnostics from JSON `error` (type, code, param, truncated message, response id prefix)
- `apps/worker/tests/test_openai_responses_adapter.py` — P7 success path, HTTP 400 redaction test

**Purpose:** OpenAI Responses `json_schema` with `strict: true` rejects Pydantic-derived schemas where not every `properties` key is listed in `required`. The production `FactsheetPayload` omits optional `key_facts` from `required`, which caused HTTP 400. The live canary now sends a minimal strict-safe schema while still validating returned JSON against the factsheet contract.

**Tests run:**

- `python3 -m pytest` — full worker suite (`apps/worker`, `PYTHONPATH=../api:.`)
- `python3 -m pytest` — full API suite (`apps/api` via sprint runner / `.venv`)
- `bash scripts/sprint_runner.sh all`

**Results:** pass (exit 0). Live canary: **1** `POST /v1/responses` → **200 OK**; `ai_runs` **completed**, `ai_stage_logs` **accepted**.

**Forbidden areas checked:**

- [x] No billing / Stripe / wallet / credit_ledger / processing-minute policy edits
- [x] No Railway deploy or env mutations (`railway variables set` not used)
- [x] No secrets in repo; no keys echoed in logs or this report
- [x] Real OpenAI: sprint-approved; **≤5** live calls after patch — **1** used (first attempt succeeded)

**Secret / key-pattern check:** `scripts/sprint_runner.sh guard` + touched-path review — **clean** (no secret literals added).

**Provider-call check:** One live OpenAI Responses call from `python -m ai.canary_runner` (non–dry-run). Tests remain mocked.

**Known risks:** Other schemas sent through the adapter with `strict: true` may still fail if nested objects omit `required` keys; only the canary path was switched to `p7-canary-v1`. Broader “strict schema normalizer” is a follow-up if more live stages ship.

**Next recommended sprint:** Extend strict-schema hardening to other contracts if/when they go live behind the same adapter, or centralize a single sanitizer for `model_json_schema()` before HTTP.

**Commands run (redact secrets):**

```bash
git checkout phase7/integration-7c1-ai-skeleton && git pull --ff-only
python3 -m pytest   # worker + api via scripts/sprint_runner.sh all
bash scripts/sprint_runner.sh all
git commit -m "fix(worker): align OpenAI canary request with Responses API"
git push origin phase7/integration-7c1-ai-skeleton
# Live canary: merged Railway worker-v2 JSON env + DATABASE_URL override from Postgres service
#   DATABASE_PUBLIC_URL (never printed) — worker-v2 has no DATABASE_PUBLIC_URL var
python3 -m ai.canary_runner --fixture tiny_transcript --job-id job_4101df665b6b
```

---

## Stage notes (sprint-specific)

### Stage 0 — git + DB sanity

- Branch at `78c8f0d` (was `b00dd10` at sprint start); clean tree after commit.
- `DATABASE_PUBLIC_URL` is **not** defined on `worker-v2` (only `DATABASE_URL` internal host). Used `Postgres-RhhK` → `DATABASE_PUBLIC_URL` for local `alembic current` and DB reads **without printing the URL**.
- `alembic current` → **008_jobstatus_sqlalchemy_labels (head)**.
- `ai_runs` with `job_4101df665b6b` and `status = 'created'` → **count 0**.

### Stage 1 — diagnose 400

- Root cause: **`strict` JSON Schema requires every property in `required`**. `FactsheetPayload.model_json_schema()` had `required: ["title","summary"]` only; `key_facts` omitted → OpenAI **400 invalid_json_schema** class of failure.

### Stage 2 — redacted request-shape summary

| Field | Value |
|--------|--------|
| Endpoint | `POST {OPENAI_BASE_URL or https://api.openai.com}/v1/responses` |
| Model | From `AI_MODEL` env (here `gpt-4.1-mini`) |
| Top-level keys | `model`, `input`, `temperature`, `max_output_tokens`, `text`, `metadata` |
| `input` shape | Array of role objects: `system` + `user`; each `content` = `[{type: "input_text", text: …}]` |
| `text.format` | `{ type: "json_schema", name: "<slug≤64>", schema: <JSON Schema object>, strict: true }` |
| Schema (canary) | Name `p7-canary-v1`, version `1.0.0`; Pydantic title `P7CanaryFactsheetLivePayload` |
| Root `type` | `object` |
| `required` count | **3** (`title`, `summary`, `key_facts`) |
| `additionalProperties` | `false` at root |
| Token fields | Request: `max_output_tokens`; response usage: `input_tokens` / `output_tokens` (fallback `prompt_tokens` / `completion_tokens`) |
| `temperature` | From `AICompletionRequest` (canary uses `0.0`) |

### Stage 5 — live canary

- **Live HTTP calls (post-patch):** **1** (cap ≤5; no retries needed).
- Exit code **0**; log line: `POST …/v1/responses "HTTP/1.1 200 OK"` (no body logged).

### Stage 6 — AIRun / AIStageLog (redacted)

- Latest **completed** run id prefix: `air_12fc08a5…` — `status=completed`, `error_code=null`.
- Stage log: `openai_canary_synthetic`, `status=completed`, `provider_name=openai`, `model_name=gpt-4.1-mini`, `input_tokens=253`, `output_tokens=78`, `validation_status=accepted`, `provider_request_id` prefix `resp_0c9a5051…` (full id stored in DB only).
- Prior failed rows retained: `openai_canary_http_bad_request` / `OpenAI HTTP 400` (pre-fix).

### Stage 7 — key rotation note

- If an OpenAI key or DB URL was ever pasted into chat, logs, or a shared JSON export, **rotate that credential** in Railway and any other stores. This report contains **no** secret values.

---

## Optional quick checklist

- [x] Sprint branch (not `main`)
- [x] `bash scripts/sprint_runner.sh all` → exit 0
- [x] No secrets / no forbidden-area drift
