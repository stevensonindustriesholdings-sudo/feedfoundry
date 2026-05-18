# FeedFoundry Hermes Agent Stack — pre-implementation capture

Captured before agent-stack code landed on `feat/feedfoundry-hermes-agent-stack`.

## 1) FeedFoundry git snapshot

```text
$ cd /Users/stevelee/Documents/feedfoundry && git status --short && git branch --show-current

feat/feedfoundry-hermes-agent-stack
```

(Working tree was clean at capture; prior branch was `feat/feedfoundry-live-customer-admin-ui`.)

## 2) CEO repo — Hermes / ACP

Requested scripts under `stevenson-skunkworks-ceo`:

- `./scripts/hermes_cursor_acp_status.sh` — **missing** (not in repo).
- `./scripts/hermes_cursor_acp_smoke.sh` — **missing** (not in repo).

Substitute / additional checks run:

```text
$ cd .../stevenson-skunkworks-ceo && bash ./scripts/04_hermes_smoke.sh
# PASS: hermes doctor + help head (non-fatal WARNs for optional integrations)

$ hermes acp --check
# PASS: "Hermes ACP check OK"
```

**Railway / Stripe / prod:** no mutations performed (read-only inspection only).

## 3) Phase 1 inspection summary

### `apps/worker/`

- **`worker.py`**: claims jobs, optional source verify, media download → `inspect_media_file` → `run_audio_extraction` (FFmpeg) → `run_transcript_pipeline_v0` → stub/core outputs including `hosted_manifest.json`, credit settlement via `_settle_processing_allowance`, `fail_job` releases reserved minutes without lifetime debit.
- **`pipeline/`**: transcript, derived outputs (chapters, CTAs, metadata, FAQs, fact sheet, hosted manifest), audio extraction, export bundle, public payloads, QA validate.
- **`providers/`**: OpenAI, Anthropic, Groq, etc. — **not used** by the new deterministic agent bundle (no live provider calls).
- **`media_inspection.py`**: ffprobe-oriented inspection.
- **Tests**: SQLite fixtures against API models/ledger; audio/FFmpeg tests mock subprocess; transcript/hosted manifest contract tests.

### `apps/worker/ai/`

- **Before:** no `ai/` package (this sprint adds `ai/feedfoundry_agents/`).

### `apps/api/`

- FastAPI routers (`health`, etc.), **`credit_ledger`**: `reserve` / `release` / `debit` processing minutes; Stripe webhook touches annual minutes — **not modified** in this work.
- No `ProductSignal` / `AIRun` symbols in repo (grep empty).

### `docs/`

- **`MVP_PARALLEL_CONTRACT.md`**: parallel lane naming, integration captain, control rod.
- **`CURSOR_PARALLEL_AGENTS_FEEDFOUNDRY.md`**: Cursor Cloud Agents playbook.
- **`SKUNKWORKS_AI_WORKER_ACCELERATION_REPORT.md`**, **`RAILWAY_AI_WORKER_DEMO_REPORT.md`**: operational notes; constraints respected here.

### `AGENTS.md`

- Product + engineering rules: no URL ingestion V1, credits/ledger, AI via router with logging — agent bundle is **rule-based / mock-labelled** and does not replace the AI router.

### Captain rules (`.cursor/rules/`)

- Product doctrine, backend architecture, AI cost controls, autonomy max, Railway allowlist, MVP rule — **unchanged**; this deliverable stays worker-local and documentation-heavy.

### Sprint board

- No Notion/sprint tool queried; repo contract docs (`MVP_PARALLEL_CONTRACT.md`) treated as the authoritative parallel-lane board.

### Search themes (grep-style)

| Theme | Finding |
|--------|---------|
| `transcript` | Core pipeline + worker stub outputs; `build_hosted_manifest_from_transcript`. |
| `ffmpeg` | `pipeline/audio_extraction.py`, `audio_extract.py`, tests; failures surface as `JobProcessingFailure` / worker errors. |
| `ProductSignal` | Not present. |
| `manifest` | `job_manifest_object_key`, `hosted_manifest.json`, `build_hosted_manifest_from_transcript`. |
| `processing_minutes` | Ledger + `_settle_processing_allowance`; failures use `release_reserved_processing_minutes` (no debit). |
| `AIRun` | Not present. |
| `router` | API `APIRouter`; worker `ai_router_probe` sidecar import. |

### FFmpeg / minutes policy (read-only confirmation)

- **`fail_job`** releases reserved allowance; **`test_fail_job_releases_reserve_without_debit`** asserts no lifetime debit on failure.
- New **FFmpeg failure classifier** returns `debit_processing_minutes: false` explicitly; **no** change to ledger policy code.

---

## Outcome

Hermes CLI present; **ACP `--check` OK**. Requested `hermes_cursor_acp_*.sh` scripts absent in CEO repo — used `04_hermes_smoke.sh` + `hermes acp --check` instead.

## Phase 12 — pytest (post-implementation)

Focused (agent bundle tests only), from `apps/worker` with `uv` + Python 3.11:

- **PASS:** `uv sync --python 3.11 --extra dev && uv run --python 3.11 -m pytest tests/test_feedfoundry_agents_*.py -q` → **10 passed**

Broader worker suite (requires API models on `PYTHONPATH`):

- **PASS:** `PYTHONPATH=../api uv run --python 3.11 -m pytest -q` → **38 passed**
