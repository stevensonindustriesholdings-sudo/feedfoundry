# Phase 7 — OpenAI canary guardrails (internal / ops)

This document describes **environment-only** guardrails for the structured worker AI layer (`apps/worker/ai/*`). It is **not** a customer-facing feature flag doc. V1 remains **mock-default** in CI and local dev; no sprint in this slice enables live OpenAI in tests.

## Mode matrix

| `AI_STRUCTURED_PROVIDER_MODE` | `AI_CANARY_ENABLED` | `AI_ENABLE_REAL_PROVIDER` | `OPENAI_API_KEY` | Numeric caps (`AI_CANARY_*`) | Outcome |
|--------------------------------|--------------------|---------------------------|------------------|------------------------------|---------|
| `mock` (default) | any | any | any | ignored | `MockAIProvider` — no HTTP |
| `disabled` | any | any | any | any | `DisabledStructuredProvider` — `complete()` raises |
| `canary` | false **or** kill-switch false | — | — | — | `ProviderDisabledError` at `get_structured_ai_provider()` |
| `canary` | true | true | non-empty | `MAX_CALLS>=1`, `MAX_COST>0`, `TIMEOUT>=1` | `OpenAIStructuredProviderShell` (HTTP still **not** wired in this repo slice; `complete()` raises `RuntimeError` until a dedicated canary sprint) |
| `canary` | true | true | **empty** | valid | `ProviderDisabledError` (fail-closed) |

**Legacy:** If `AI_STRUCTURED_PROVIDER_MODE` is unset and `AI_ENABLE_MOCK_PROVIDER` is false, mode resolves to `disabled` (replacing the old `NotImplementedError` on registry access with a `DisabledStructuredProvider` instance).

## Kill-switch and rollback

1. **Immediate off:** set `AI_STRUCTURED_PROVIDER_MODE=mock` (or `disabled`).
2. **Block real SDK paths:** set `AI_ENABLE_REAL_PROVIDER=false` (kill-switch).
3. **Disable canary lane:** set `AI_CANARY_ENABLED=false`.
4. **Remove credentials:** unset or blank `OPENAI_API_KEY` in the worker environment.

No code deploy is required for rollback if your platform already reads env at boot; restart workers after env changes.

## Environment table (placeholders only)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Server-side secret; empty in repo templates. Required only when mode is `canary` and all gates pass. |
| `AI_PROVIDER` | YAML / legacy routing hint (e.g. `openai`); **not** the structured mode selector. |
| `AI_STRUCTURED_PROVIDER_MODE` | `mock` \| `canary` \| `disabled` |
| `AI_ENABLE_REAL_PROVIDER` | Kill-switch; must be truthy for canary resolution to succeed. |
| `AI_CANARY_ENABLED` | Master canary toggle. |
| `AI_CANARY_MAX_CALLS` | Must be ≥ 1 when using canary. |
| `AI_CANARY_MAX_COST` | Must be > 0 (internal ceiling hint for ops metrics). |
| `AI_CANARY_TIMEOUT_SECONDS` | Must be ≥ 1. |

## First real-provider canary (later sprint)

When Captain approves a **tiny** staging-only canary (see `docs/CAPTAIN_RULES.md`):

1. Minimal transcript or JSON fixture; **one** structured call through the router with full logging.
2. Validator / governor must pass before treating output as customer-visible.
3. No customer path on the first canary.
4. Keep `AI_STRUCTURED_PROVIDER_MODE=mock` in CI; enable canary only in the controlled environment with explicit caps.

## Code references

- API policy: `apps/api/app/services/ai_internal_policy.py` — `AICanaryGateConfig`, `load_ai_canary_gate_config_from_env`.
- Worker mode + registry: `apps/worker/ai/provider_mode.py`, `apps/worker/ai/registry.py`.
- Adapter shell: `apps/worker/ai/openai_adapter.py` (no SDK imports at load time).