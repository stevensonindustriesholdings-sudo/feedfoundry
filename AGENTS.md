# FeedFoundry Agent Rules

You are building FeedFoundry, a creator archive intelligence product.

## Non-negotiable product constraints

- V1 does not ingest from URLs.
- Creators upload their own source media files.
- The system accepts video/audio/podcast/TikTok-style files, not external links.
- Base44 is the customer-facing product and dashboard layer.
- Railway hosts the FastAPI backend, processing worker, Postgres, and optional Redis.
- Python and FFmpeg are the processing core.
- OpenAI is the baseline AI provider, but the architecture must support multiple AI providers.
- The commercial model is annual access/hosting plus processing credits.
- Do not frame this as monthly SaaS/MRR.
- Every job must estimate, reserve, debit, release, or refund credits.
- API keys must never be exposed to browser/client code.
- Every AI call must pass through budget, token, retry, and provider routing controls.

## Engineering rules

- Prefer simple, readable Python.
- Use FastAPI for the backend API.
- Use Postgres as the source of truth.
- Use SQLAlchemy or SQLModel, but keep models explicit and boring.
- Write tests for credit ledger logic, job state transitions, and AI routing.
- Do not build speculative features unless they are needed by the MVP.
- Do not introduce URL ingestion.
- Do not hardcode provider secrets.
- Keep all config in environment variables or config tables.
- Use structured JSON outputs for AI-generated assets.
- Every provider response must log estimated input tokens, output tokens, cost estimate, latency, model, provider, and job_id.

## UI boundary

Do not overbuild the frontend in this repository. Generate OpenAPI-compatible endpoints and simple API documentation for Base44 to consume.

## Control pack / sprint contract

- **One agent = one bounded sprint; one branch per sprint.** No unrelated edits; stop at the sprint goal.
- **No secrets:** never commit API keys, tokens, or real `.env` values; never put provider keys in the browser or client bundles.
- **Customer AI output** only after validator/governor checks in the pipeline—not raw model dumps.
- **Provider policy:** mock provider remains the default in documented policy and local practice; real providers only behind explicit environment flags. Tests and CI must not call real providers unless a sprint explicitly approves that (document the exception when it exists).
- **No processing-minute / credit-ledger / billing changes** without an explicit sprint scoped to that work.
- **No Railway deployment or config mutations** from routine sprints; infrastructure changes are their own approved scope.
- **References:** `docs/CAPTAIN_RULES.md` (captain operating contract, branch naming, forbidden areas, canary checklist), `docs/REPORT_TEMPLATE.md` (sprint report fields), `docs/SPRINT_BOARD.md` (near-term sequence), `scripts/sprint_report.sh` (quick branch/diff context), `scripts/sprint_runner.sh` (checkpoint / guard / report grouping for Sprint Runner Mode), `.github/pull_request_template.md` (PR checklist).

## Autonomy Level 1.5 (Sprint Runner Mode)

Use this mode for bounded sprints so the agent batches safe local work instead of asking for repeated approvals on every micro-step.

- **Batch safe locals without re-asking** when the environment allows: `cd` to repo root, `git status`, `git log`, `git diff`, read-only file reads, `pytest`, `npm run lint` / `typecheck` / `build`, `bash -n` on scripts, scoped `mkdir`/`chmod` on sprint artifacts, and **one grouped** `scripts/sprint_runner.sh all` at checkpoint, after implementation, and before handoff.
- **Prefer `scripts/sprint_runner.sh`** over ad-hoc terminal whack-a-mole: `checkpoint` (context), `guard` (branch + diff hygiene + key-pattern scan), `report` (wraps `sprint_report.sh` when present), then `all` in order.
- **One grouped pattern per sprint leg:** checkpoint → implement → final guard + report + commit (+ push only the sprint branch when the sprint explicitly allows push and guard is clean).

### Still STOP (no agent autonomy)

Do **not** do these without explicit human approval for that action: **push to `main`**, **merge to `main`**, **`git rebase`**, **`git reset --hard`**, **`git clean`**, **`rm -rf`** (especially project trees), **`sudo`**, **package installs** (`npm install` / `pip install` / `brew` when not in sprint scope), **`curl` / `wget`**, **`ssh`**, **`docker`**, **Railway mutations** (deploy, variables, service changes), **Stripe / live billing**, **live OpenAI or other real provider calls**, **DB migrations / destructive DB ops**, **printing or committing secrets**, **writes outside the repo**, **arbitrary `git merge`** (fast-forward `git pull --ff-only` to sync a branch is OK when the sprint allows network and the sprint branch is behind).

See `docs/CAPTAIN_RULES.md` for the full captain contract and forbidden areas.
