# AI cost controls

Policy is defined in `ai-routing.yaml` at the repo root and mirrored by env-based monthly USD ceilings (`DEV_MONTHLY_AI_BUDGET_USD`, etc.).

## Rules

1. Every call passes through the AI router with explicit limits and fallbacks.
2. Log every attempt to `ai_usage_logs` with tokens, latency, cost estimate, provider, model, module, job id, retries, and rate-limit headers when present.
3. Hard-stop or throttle when global or per-job budgets would be exceeded (`fail_closed_on_missing_cost_estimate`, `fail_closed_on_missing_credit_reservation`).
4. Model names are **only** read from environment variables referenced in YAML (`model_env`), never hardcoded in Python.

## Worker concurrency

Cap concurrent AI calls per worker via `max_concurrent_ai_calls_per_worker` in YAML and `MAX_CONCURRENT_JOBS_PER_WORKER` in env.
