# Phase 7 — OpenAI canary guardrails (internal / ops)

This document describes **environment-only** guardrails for the structured worker AI layer (`apps/worker/ai/*`). It is **not** a customer-facing feature flag doc. V1 remains **mock-default** in CI and local dev; **tests never call the live OpenAI network** (httpx is mocked).

## Mode matrix

| `AI_STRUCTURED_PROVIDER_MODE` | `AI_PROVIDER` | `AI_CANARY_ENABLED` | `AI_ENABLE_REAL_PROVIDER` | `OPENAI_API_KEY` | Numeric caps (`AI_CANARY_*`) | `FF_OPENAI_CANARY_RUNNER_ENABLED` | Outcome |
|------------------------------|---------------|----------------------|---------------------------|------------------|------------------------------|-------------------------------------|---------|
| `mock` (default) | any | any | any | any | ignored | ignored | `MockAIProvider` — no HTTP |
| `disabled` | any | any | any | any | any | any | `DisabledStructuredProvider` — `complete()` raises |
| `canary_openai` (alias `canary`) | **must be `openai`** | false **or** kill-switch false | — | — | — | — | `ProviderDisabledError` at `get_structured_ai_provider()` |
| `canary_openai` | `openai` | true | true | non-empty | `MAX_CALLS>=1`, `MAX_COST>0`, `TIMEOUT>=1` | any | `OpenAIStructuredProviderShell` constructed; `complete()` **blocked** until runner flag is on |
| `canary_openai` | `openai` | true | true | non-empty | valid | **true** | `complete()` may issue **one bounded** `POST {OPENAI_BASE_URL}/v1/responses` (Responses API, `text.format` JSON schema from `SCHEMA_REGISTRY`) |
| `canary_openai` | `openai` | true | true | **empty** | valid | any | `ProviderDisabledError` (fail-closed) |
| `canary_openai` | `anthropic` (etc.) | true | true | non-empty | valid | any | `ProviderDisabledError` — `[ai_canary_ai_provider_not_openai]` |

**Legacy:** If `AI_STRUCTURED_PROVIDER_MODE` is unset and `AI_ENABLE_MOCK_PROVIDER` is false, mode resolves to `disabled` (replacing the old `NotImplementedError` on registry access with a `DisabledStructuredProvider` instance).

## Kill-switch and rollback

1. **Immediate off:** set `AI_STRUCTURED_PROVIDER_MODE=mock` (or `disabled`).
2. **Block real SDK paths:** set `AI_ENABLE_REAL_PROVIDER=false` (kill-switch).
3. **Disable canary lane:** set `AI_CANARY_ENABLED=false`.
4. **Remove credentials:** unset or blank `OPENAI_API_KEY` in the worker environment.
5. **Routing hint:** set `AI_PROVIDER=openai` explicitly for the structured OpenAI canary path (empty or non-`openai` values fail closed).
6. **Disable fixture runner HTTP:** set `FF_OPENAI_CANARY_RUNNER_ENABLED=false` (blocks `complete()` HTTP even if other gates are on).

No code deploy is required for rollback if your platform already reads env at boot; restart workers after env changes.

## Fail-closed error codes (worker)

Machine-readable prefixes appear in `ProviderDisabledError` messages as `[code] …`:

| Code | Meaning |
|------|---------|
| `ai_canary_kill_switch_off` | `AI_CANARY_ENABLED` and/or `AI_ENABLE_REAL_PROVIDER` not both truthy |
| `ai_canary_numeric_caps_invalid` | `AI_CANARY_MAX_CALLS`, `AI_CANARY_MAX_COST`, or `AI_CANARY_TIMEOUT_SECONDS` out of range |
| `ai_canary_ai_provider_not_openai` | `AI_PROVIDER` is not exactly `openai` |
| `ai_canary_openai_api_key_missing` | `OPENAI_API_KEY` empty or whitespace |
| `ai_canary_structured_mode_not_canary` | `AI_STRUCTURED_PROVIDER_MODE` is not `canary_openai` (or legacy `canary`) |
| `ai_canary_runner_flag_off` | `FF_OPENAI_CANARY_RUNNER_ENABLED` is not truthy (HTTP path off) |

After HTTP is attempted, transport failures use `CanaryRuntimeCode` values such as `openai_canary_http_auth`, `openai_canary_http_rate_limit`, `openai_canary_http_timeout`, `openai_canary_http_malformed_response`, etc. Legacy `openai_canary_adapter_http_not_wired` remains for unexpected `RuntimeError` paths outside the typed adapter.

## Tiny canary runner (synthetic fixture only)

Separate from `FF_WORKER_AI_ENRICHMENT_ENABLED`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FF_OPENAI_CANARY_RUNNER_ENABLED` | off (`false`) | When **true**, after a job’s mock enrichment (if any), the worker may run `ai.canary_runner.maybe_run_openai_canary_job_runner` using **only** the checked-in text fixture `apps/worker/ai/fixtures/canary_synthetic_transcript.txt` — never arbitrary customer transcript text. Still requires full structured OpenAI canary gates + `canary_openai` mode. |

## Bounded HTTP adapter (Responses API)

- **Endpoint:** `POST {OPENAI_BASE_URL or https://api.openai.com}/v1/responses`.
- **Structured output:** `text.format` with `type: json_schema`, `schema` from Pydantic `model_json_schema()` for `(schema_name, schema_version)` in `SCHEMA_REGISTRY`.
- **Timeout:** `min(request.timeout_seconds, AI_CANARY_TIMEOUT_SECONDS)` per call; `httpx` client timeout matches that bound.
- **Retries:** `AI_CANARY_HTTP_MAX_RETRIES` (default **0**); bounded retries only on HTTP 429 / 5xx when retries > 0.
- **Logging:** no raw prompts or bodies; info logs include model, stage, trace_id, URL only.
- **API policy helper:** `structured_openai_canary_policy_allows_http_preconditions()` in `ai_internal_policy.py` mirrors booleans, numerics, and `AI_PROVIDER` (excludes API key and runner flag).

## Environment table (placeholders only)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Server-side secret; empty in repo templates. Required only when mode is `canary_openai` and all gates pass. |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible base (no trailing slash); default `https://api.openai.com`. |
| `AI_PROVIDER` | Must be `openai` for the structured OpenAI canary path (YAML / routing hint shared with legacy AI config). |
| `AI_STRUCTURED_PROVIDER_MODE` | `mock` \| `canary_openai` \| `disabled` (legacy alias: `canary` → `canary_openai`) |
| `AI_ENABLE_REAL_PROVIDER` | Kill-switch; must be truthy for canary resolution to succeed. |
| `AI_CANARY_ENABLED` | Master canary toggle. |
| `AI_CANARY_MAX_CALLS` | Must be ≥ 1 when using canary. |
| `AI_CANARY_MAX_COST` | Must be > 0 (internal ceiling hint for ops metrics). |
| `AI_CANARY_TIMEOUT_SECONDS` | Must be ≥ 1. |
| `AI_CANARY_HTTP_MAX_RETRIES` | Optional; default `0` (no HTTP retries). |
| `FF_OPENAI_CANARY_RUNNER_ENABLED` | Ops-only; enables the fixture-bound canary runner and allows `OpenAIStructuredProviderShell.complete()` HTTP (default **false**). |

## First real-provider canary (later sprint)

When Captain approves a **tiny** staging-only canary (see `docs/CAPTAIN_RULES.md`):

1. Minimal transcript or JSON fixture; **one** structured call through the router with full logging.
2. Validator / governor must pass before treating output as customer-visible.
3. No customer path on the first canary.
4. Keep `AI_STRUCTURED_PROVIDER_MODE=mock` in CI; enable `canary_openai` only in the controlled environment with explicit caps.

**Next operational step after this sprint:** first **manually triggered** staging canary (fixture runner + env gates), not a broad rollout.

## Code references

- API policy: `apps/api/app/services/ai_internal_policy.py` — `AICanaryGateConfig`, `load_ai_canary_gate_config_from_env`, `ai_provider_allows_openai_structured_path`, `structured_openai_canary_policy_allows_http_preconditions`.
- Worker mode + registry: `apps/worker/ai/provider_mode.py`, `apps/worker/ai/registry.py`, `apps/worker/ai/openai_canary_gates.py`.
- Adapter: `apps/worker/ai/openai_adapter.py` (httpx Responses client; no OpenAI SDK).
- Fixture runner: `apps/worker/ai/canary_runner.py`.
