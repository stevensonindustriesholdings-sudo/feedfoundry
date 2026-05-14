# Sprint report 7C-13 → 7C-16 — Live worker AI E2E closeout bundle

**Captain Autonomy Rules v1.5** — branch `phase7/integration-7c1-ai-skeleton`.

---

## Sprint report

**Branch name:** `phase7/integration-7c1-ai-skeleton`  
**Commit hash:** tip `52a9e2d` (`git log -3 --oneline` on this branch).

**Files changed:**

- `apps/worker/ai/openai_adapter.py` — production factsheet OpenAI requests use strict-safe `P7CanaryFactsheetLivePayload` JSON Schema on the wire; validation unchanged (`FactsheetPayload`).
- `apps/worker/ai/openai_canary_gates.py` — HTTP gate allows `FF_OPENAI_CANARY_RUNNER_ENABLED` **or** `FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE`.
- `apps/worker/ai/registry.py` — docstring aligned with dual HTTP unlock.
- `apps/worker/ai/pipeline.py` — optional bounded OpenAI for `transcript_intelligence` when enrichment + live flags and canary gates pass; `extra_json` stores redacted digest (`live_openai_completions_used`, `artifact_digest` char counts only); `OpenAIHTTPAdapterError` → failed stage log; visual/product remain mock.
- `apps/worker/tests/test_openai_responses_adapter.py`, `test_openai_canary_guardrails.py`, `test_mock_ai_pipeline_integration.py` — gate + adapter + enrichment coverage.
- `docs/phase7-openai-canary.md`, `docs/phase7-mock-ai-worker-pipeline.md`, this file.

**Purpose:** Close Phase 7C live-path wiring so **worker job enrichment** can exercise **real OpenAI** for transcript intelligence under the same fail-closed gates as the fixture canary, with a **hard per-run completion cap**, mock default unchanged, and no ledger touch.

**Tests run:**

- `apps/api`: `python -m pytest` (72 passed)
- `apps/worker`: `python -m pytest` (112 passed)
- `bash scripts/sprint_runner.sh all` (exit 0)

**Results:** pass

**Forbidden areas checked:**

- [x] No billing / Stripe / wallet / credit_ledger / processing-minute policy edits
- [x] No Railway deploy or env mutations (read-only variable merge for local smoke only)
- [x] No secrets in repo; no client-side provider keys
- [x] Mock default; live calls only sprint-approved env on staging DB smoke

**Secret / key-pattern check:** Grep `apps/worker/ai` for `sk-[a-zA-Z0-9]{10,}` — **clean** (tests use short placeholders outside `ai/`).

**Provider-call check (live, this sprint):**

| Metric | Value |
|--------|--------|
| **live_call_count (total bundle)** | **1** |
| **Mechanism** | Staging DB smoke: `maybe_run_mock_ai_job_enrichment` for `job_4101df665b6b` with merged `worker-v2` + `Postgres-RhhK` env; `FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS=1`, `FF_OPENAI_CANARY_RUNNER_ENABLED=false`, `AI_CANARY_HTTP_MAX_RETRIES=0`. |
| **AIRun id prefix** | `air_dc2d3683` |
| **Transcript stage** | `completed`, `provider_name=openai`, `model_name=gpt-4.1-mini`, `live_openai_completions_used=1`, `artifact_count=4` (one chunk: factsheet live + FAQ/chapters/metadata mock). |
| **Tokens / cost** | Redacted aggregates only; per policy not pasted here. |

CI and local pytest remain **mock-only** (httpx patched; no live HTTP).

**Known risks:**

- OpenAI `strict` may still reject other schemas if expanded beyond current registry shapes; factsheet is the known strict edge case addressed here.
- Raising `FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS` increases live spend linearly with chunk count × schemas.

**Next recommended sprint (7D-1):** **Admin / customer visibility** (`docs/SPRINT_BOARD.md` row 5) — dashboards and status surfaces aligned with `docs/phase7-ai-run-visibility.md` and internal admin redaction tests (`apps/api/tests/test_admin_ai_runs_visibility.py`); still no secrets in client bundles.

**Commands run (redact secrets):**

```text
git checkout phase7/integration-7c1-ai-skeleton && git pull --ff-only
alembic current → 008_jobstatus_sqlalchemy_labels (head) via venv alembic + DATABASE_PUBLIC_URL from Postgres-RhhK (URL never printed)
PYTHONPATH=../api:. python -m pytest (api + worker full suites)
bash scripts/sprint_runner.sh all
# Staged enrichment smoke: python child process with railway variables merge (stdout: AIRun prefix, TI status, LIVE_USED only)
```

---

## Stage notes

### 7C-13 — Real OpenAI in worker enrichment path

- Implemented dual HTTP unlock + budgeted hybrid provider for transcript intelligence only.
- Staging smoke confirmed one live `POST …/v1/responses` and validated stage log (no stuck job in this path; enrichment is post-`JobOutput` write in `worker.py`).

### 7C-14 — Output pack

- **Transcript intelligence:** validated artifacts summarized in `AIStageLog.extra_json` (`artifact_digest` with char counts / list sizes only — no raw transcript blobs).
- **Factsheet-like:** first schema in the TI sequence (factsheet) satisfied via live call when budget allows; remainder via mock; all contracts pass `OutputValidator`.
- **FAQ / chapters / metadata:** same TI pipeline modules; when budget exhausted after factsheet, subsequent schemas use mock (logged via `live_openai_completions_used`).
- **Public promotion gap:** customer `JobOutput` JSON is unchanged by this sprint; TI lives in internal `AIRun` / `AIStageLog` only.

### 7C-15 — Hardening

- Tests: mock default, gate fail-closed, enrichment live without key → mock + no httpx, HTTP unlocked by `FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE` without fixture runner, existing cancellation / validation / no-ledger tests retained.
- Admin redaction: unchanged; cited `test_admin_ai_runs_visibility.py`.

### 7C-16 — Docs + push

- This report + phase7 doc touch-ups.
