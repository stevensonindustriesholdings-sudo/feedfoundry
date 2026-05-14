# Sprint report — 7C-12C (filled from `docs/REPORT_TEMPLATE.md`)

**Captain Autonomy Rules v1.5** — Sprint **7C-12C — five-call OpenAI canary repeatability batch**

---

## Sprint report

**Branch name:** `phase7/integration-7c1-ai-skeleton`  
**Commit hash:** *(updated at commit; see `git log -1` on branch tip after push)*

**Files changed:**

- `docs/SPRINT_REPORT_7C_12C.md` — this sprint record only (no code or policy edits).

**Purpose:** Run **five sequential** live OpenAI Responses canary invocations (`--fixture tiny_transcript`, `--job-id job_4101df665b6b`) against staging DB and gates, stopping the batch on first hard failure. Confirm repeatability after 7C-12B schema/adapter fixes.

**Tests run:**

- `bash scripts/sprint_runner.sh all` — checkpoint, guard, API pytest (72 passed), worker pytest (110 passed), report.

**Results:** pass (exit 0). Live canary: **5** sequential `POST /v1/responses` → **HTTP 200** each; five new `ai_runs` **completed** with `ai_stage_logs` **accepted** and stable input token count.

**Forbidden areas checked:**

- [x] No billing / Stripe / wallet / credit_ledger / processing-minute policy edits
- [x] No Railway deploy or env mutations (`railway variables set` not used)
- [x] No secrets in repo; no keys, DB URLs, raw prompts, or provider bodies with customer text in this report
- [x] Real OpenAI: sprint-approved; **5** live calls (at cap **5** additional); sequential; batch stopped only after all five succeeded

**Secret / key-pattern check:** `bash scripts/sprint_runner.sh guard` (clean) plus scoped `rg` / `grep` on `apps/api`, `apps/worker`, `docs`, `README.md`, `.env.example`, `scripts` — hits are **env var names**, documentation, test placeholders (`sk-test-placeholder`, `sk_test_fake`), or guard-script comments — **no committed secret literals**.

**Provider-call check:** Five live OpenAI Responses calls from `python -m ai.canary_runner` (non–dry-run). CI pytest remains mocked / offline.

**Known risks:** Canary logs include **public** OpenAI URL and **job id** in `trace_id` (fixture path only; no arbitrary customer transcript in logs). If logs are ever exported broadly, treat `trace_id` as operational metadata.

**Next recommended sprint:** Same as 7C-12B follow-up — extend strict-schema hardening to other live contracts if more stages use `json_schema` + `strict: true`.

**Commands run (redact secrets):**

```bash
git checkout phase7/integration-7c1-ai-skeleton && git pull --ff-only origin phase7/integration-7c1-ai-skeleton
# Child-only env: merge `railway variable list -s worker-v2 --json` + `DATABASE_PUBLIC_URL` from `Postgres-RhhK` (never printed); `DATABASE_URL` overridden for local TCP to public Postgres URL.
# `apps/api/.venv/bin/python -m alembic current` under `apps/api` with merged env
# Five times from `apps/worker`: PYTHONPATH=../api:. …/python -m ai.canary_runner --fixture tiny_transcript --job-id job_4101df665b6b
bash scripts/sprint_runner.sh all
git commit -m "docs(phase7): record OpenAI repeatability canary batch"
git push origin phase7/integration-7c1-ai-skeleton
```

---

## Stage notes (sprint-specific)

### Stage 1 — git

- Tip at run: `5533352` or later; working tree **clean** before doc commit.

### Stage 2 — alembic current

- Merged Railway `worker-v2` variables with `DATABASE_PUBLIC_URL` from `Postgres-RhhK` for local DB (same pattern as 7C-12B). **Never printed** `DATABASE_URL` / `DATABASE_PUBLIC_URL`.
- `alembic current` → **`008_jobstatus_sqlalchemy_labels (head)`**.

### Stage 3 — job suitability

- `jobs` row for `job_4101df665b6b`: **count 1** (suitable).

### Stage 4 — five live calls (newest → oldest in DB)

| Call | Exit | AIRun id prefix | AIStageLog id prefix | Run / stage status | validation | Model | Response id prefix | In tok | Out tok | Stage error |
|-----:|-----:|-----------------|----------------------|--------------------|------------|-------|--------------------|-------:|--------:|-------------|
| 1 | 0 | `air_33eda85a13…` | `ais_ba6f3e3353…` | completed / completed | accepted | gpt-4.1-mini | `resp_03c06643e…` | 253 | 82 | — |
| 2 | 0 | `air_15c8fdd754…` | `ais_41e27ebe9f…` | completed / completed | accepted | gpt-4.1-mini | `resp_0d9c6093f…` | 253 | 78 | — |
| 3 | 0 | `air_cf04486bd8…` | `ais_c365e6971d…` | completed / completed | accepted | gpt-4.1-mini | `resp_0355837ee…` | 253 | 78 | — |
| 4 | 0 | `air_c0628a2924…` | `ais_ee41925d95…` | completed / completed | accepted | gpt-4.1-mini | `resp_06df3644d…` | 253 | 78 | — |
| 5 | 0 | `air_53a054c350…` | `ais_49263734d0…` | completed / completed | accepted | gpt-4.1-mini | `resp_0efe30764…` | 253 | 77 | — |

- Stderr per call: adapter request line (model, stage, **trace_id**, public API URL) + httpx **200 OK** — no response body or Authorization material logged.

### Stage 5 — key rotation note

- No customer payload or secrets were pasted into this report. If any OpenAI key or DB URL appeared in a shared terminal buffer or earlier accidental `head` of Railway JSON, **rotate** that credential in Railway. Routine canary logs should remain ops-scoped.

---

## Optional quick checklist

- [x] Sprint branch (not `main`)
- [x] `bash scripts/sprint_runner.sh all` → exit 0
- [x] No secrets / no forbidden-area drift
