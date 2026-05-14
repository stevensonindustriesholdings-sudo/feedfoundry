# Phase 7 — OpenAI canary guardrails (internal / ops)

This document describes **environment-only** guardrails for the structured worker AI layer (`apps/worker/ai/*`). It is **not** a customer-facing feature flag doc. V1 remains **mock-default** in CI and local dev; no sprint in this slice enables live OpenAI in tests.

## Mode matrix

| `AI_STRUCTURED_PROVIDER_MODE` | `AI_PROVIDER` | `AI_CANARY_ENABLED` | `AI_ENABLE_REAL_PROVIDER` | `OPENAI_API_KEY` | Numeric caps (`AI_CANARY_*`) | Outcome |
|------------------------------|---------------|----------------------|---------------------------|------------------|------------------------------|---------|
| `mock` (default) | any | any | any | any | ignored | `MockAIProvider` — no HTTP |
| `disabled` | any | any | any | any | any | `DisabledStructuredProvider` — `complete()` raises |
| `canary_openai` (alias `canary`) | **must be `openai`** | false **or** kill-switch false | — | — | — | `ProviderDisabledError` at `get_structured_ai_provider()` |
| `canary_openai` | `openai` | true | true | non-empty | `MAX_CALLS>=1`, `MAX_COST>0`, `TIMEOUT>=1` | `OpenAIStructuredProviderShell` (HTTP still **not** wired in this repo slice; `complete()` raises `RuntimeError` until a dedicated canary sprint) |
| `canary_openai` | `openai` | true | true | **empty** | valid | `ProviderDisabledError` (fail-closed) |
| `canary_openai` | `anthropic` (etc.) | true | true | non-empty | valid | `ProviderDisabledError` — `[ai_canary_ai_provider_not_openai]` |

**Legacy:** If `AI_STRUCTURED_PROVIDER_MODE` is unset and `AI_ENABLE_MOCK_PROVIDER` is false, mode resolves to `disabled` (replacing the old `NotImplementedError` on registry access with a `DisabledStructuredProvider` instance).

## Kill-switch and rollback

1. **Immediate off:** set `AI_STRUCTURED_PROVIDER_MODE=mock` (or `disabled`).
2. **Block real SDK paths:** set `AI_ENABLE_REAL_PROVIDER=false` (kill-switch).
3. **Disable canary lane:** set `AI_CANARY_ENABLED=false`.
4. **Remove credentials:** unset or blank `OPENAI_API_KEY` in the worker environment.
5. **Routing hint:** set `AI_PROVIDER=openai` explicitly for the structured OpenAI canary path (empty or non-`openai` values fail closed).

No code deploy is required for rollback if your platform already reads env at boot; restart workers after env changes.

## Fail-closed error codes (worker)

Machine-readable prefixes appear in `ProviderDisabledError` messages as `[code] …`:

| Code | Meaning |
|------|---------|
| `ai_canary_kill_switch_off` | `AI_CANARY_ENABLED` and/or `AI_ENABLE_REAL_PROVIDER` not both truthy |
| `ai_canary_numeric_caps_invalid` | `AI_CANARY_MAX_CALLS`, `AI_CANARY_MAX_COST`, or `AI_CANARY_TIMEOUT_SECONDS` out of range |
| `ai_canary_ai_provider_not_openai` | `AI_PROVIDER` is not exactly `openai` |
| `ai_canary_openai_api_key_missing` | `OPENAI_API_KEY` empty or whitespace |

After gates pass, the adapter shell may still record `openai_canary_adapter_http_not_wired` on the **tiny canary runner** stage until HTTP is implemented.

## Tiny canary runner (synthetic fixture only)

Separate from `FF_WORKER_AI_ENRICHMENT_ENABLED`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `FF_OPENAI_CANARY_RUNNER_ENABLED` | off (`false`) | When **true**, after a job’s mock enrichment (if any), the worker may run `ai.canary_runner.maybe_run_openai_canary_job_runner` using **only** the checked-in text fixture `apps/worker/ai/fixtures/canary_synthetic_transcript.txt` — never arbitrary customer transcript text. Still requires full structured OpenAI canary gates + `canary_openai` mode. |

## Environment table (placeholders only)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Server-side secret; empty in repo templates. Required only when mode is `canary_openai` and all gates pass. |
| `AI_PROVIDER` | Must be `openai` for the structured OpenAI canary path (YAML / routing hint shared with legacy AI config). |
| `AI_STRUCTURED_PROVIDER_MODE` | `mock` \| `canary_openai` \| `disabled` (legacy alias: `canary` → `canary_openai`) |
| `AI_ENABLE_REAL_PROVIDER` | Kill-switch; must be truthy for canary resolution to succeed. |
| `AI_CANARY_ENABLED` | Master canary toggle. |
| `AI_CANARY_MAX_CALLS` | Must be ≥ 1 when using canary. |
| `AI_CANARY_MAX_COST` | Must be > 0 (internal ceiling hint for ops metrics). |
| `AI_CANARY_TIMEOUT_SECONDS` | Must be ≥ 1. |
| `FF_OPENAI_CANARY_RUNNER_ENABLED` | Ops-only; enables the fixture-bound canary runner (default **false**). |

## First real-provider canary (later sprint)

When Captain approves a **tiny** staging-only canary (see `docs/CAPTAIN_RULES.md`):

1. Minimal transcript or JSON fixture; **one** structured call through the router with full logging.
2. Validator / governor must pass before treating output as customer-visible.
3. No customer path on the first canary.
4. Keep `AI_STRUCTURED_PROVIDER_MODE=mock` in CI; enable `canary_openai` only in the controlled environment with explicit caps.

## Code references

- API policy: `apps/api/app/services/ai_internal_policy.py` — `AICanaryGateConfig`, `load_ai_canary_gate_config_from_env`, `ai_provider_allows_openai_structured_path`.
- Worker mode + registry: `apps/worker/ai/provider_mode.py`, `apps/worker/ai/registry.py`, `apps/worker/ai/openai_canary_gates.py`.
- Adapter shell: `apps/worker/ai/openai_adapter.py` (no SDK imports at load time).
- Fixture runner: `apps/worker/ai/canary_runner.py`.
