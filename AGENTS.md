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
- **References:** `docs/CAPTAIN_RULES.md` (captain operating contract, branch naming, forbidden areas, canary checklist), `docs/REPORT_TEMPLATE.md` (sprint report fields), `docs/SPRINT_BOARD.md` (near-term sequence), `scripts/sprint_report.sh` (quick branch/diff context), `.github/pull_request_template.md` (PR checklist).
