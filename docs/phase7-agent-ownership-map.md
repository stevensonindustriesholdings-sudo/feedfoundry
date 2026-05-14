# Phase 7 — Cursor build agent ownership map

**Distinction:** **Cursor agent** = parallel human-directed coding workstream. **FeedFoundry AI module** = worker logic (Captain, Producer, etc.) — see `docs/ai-operating-brief.md`.

**Baseline branch:** `main` (post PR #3). New work should branch from latest `main` unless Captain directs otherwise.

---

## Suggested branch / worktree names

| Cursor agent | Branch | Worktree folder (example) |
|--------------|--------|---------------------------|
| Captain / Integration | `phase7/captain-ai-operating-brief` | `feedfoundry-phase7-captain` (optional) |
| Agent A — API AI state | `phase7/agent-a-api-ai-state` | `feedfoundry-agent-a-p7` |
| Agent B — Worker AI | `phase7/agent-b-worker-ai-orchestrator` | `feedfoundry-agent-b-p7` |
| Agent C — UI | `phase7/agent-c-ai-ui-product-grid` | `feedfoundry-agent-c-p7` |
| Agent D — Cost / storage | `phase7/agent-d-ai-cost-storage` | `feedfoundry-agent-d-p7` |
| Agent E — Tests / evals | `phase7/agent-e-ai-tests-evals` | `feedfoundry-agent-e-p7` |
| Agent F — Docs | `phase7/agent-f-ai-docs-runbook` | `feedfoundry-agent-f-p7` |

Worktrees are **optional**; single repo with sequential branches is acceptable if Captain prefers lower parallelism.

---

## Ownership matrix

### Agent A — API / job / output state for AI runs

| | |
|--|--|
| **Allowed** | `apps/api/app/models.py`, `apps/api/app/schemas/`, `apps/api/app/routes/` (AI status/readiness only), `apps/api/alembic/versions/`, `apps/api/tests/` |
| **Forbidden** | `apps/web/src/**` (product UI except by separate agreement), provider SDK usage in routes, worker orchestration internals |
| **Deliverables** | AI run / stage / output linkage models; readiness APIs; optional product signal/manifest output kinds; migrations + tests |
| **Conflict risk** | **High** with B on shared types; **High** with D on ledger/caps — merge A after B skeleton + E tests, coordinate with D |

### Agent B — Worker AI orchestrator / provider abstraction

| | |
|--|--|
| **Allowed** | `apps/worker/**`, `apps/worker/tests/` |
| **Forbidden** | `apps/web/**`, billing policy implementation in worker without D contract, API routes |
| **Deliverables** | Captain orchestrator; `AIProvider` adapter + mock; chunking; module skeletons; flags; no real provider in CI |
| **Conflict risk** | **High** with A on job/output schema; coordinate interfaces first |

### Agent C — Frontend / admin / customer visibility

| | |
|--|--|
| **Allowed** | `apps/web/src/**`, `apps/web/README.md`, `apps/web/.env.example` |
| **Forbidden** | `apps/api/**`, `apps/worker/**`, migrations |
| **Deliverables** | AI stage status UI; output readiness; optional product grid **preview** copy; flat errors; **no provider keys** |
| **Conflict risk** | **Medium** — depends on A API shape; ship after A exposes stable contract |

### Agent D — Cost / rate-limit / accounting / storage policy

| | |
|--|--|
| **Allowed** | `apps/api/app/services/` (caps, config), coordinated worker helpers, storage adapter touchpoints if already present, `apps/api/tests/`, env examples with **placeholders** |
| **Forbidden** | UI, unrelated full `credit_ledger` rewrite without explicit approval, provider-specific model selection logic (belongs in B adapter) |
| **Deliverables** | AI caps model; routing/cost log persistence design; storage portability notes in code comments + tests; **AI cost vs processing minutes** doc answers implemented as config when approved |
| **Conflict risk** | **High** with A on DB fields; **High** with existing ledger — small incremental changes only |

### Agent E — Tests / evals / mock provider

| | |
|--|--|
| **Allowed** | `apps/api/tests/`, `apps/worker/tests/`, `fixtures/`, golden/eval assets |
| **Forbidden** | Production shortcuts, real provider calls, real secrets |
| **Deliverables** | Mock tests, schema tests, transcript/visual/product fixtures, cap/cancel/malformed JSON tests |
| **Conflict risk** | **Low** if merged frequently |

### Agent F — Docs / env / runbook

| | |
|--|--|
| **Allowed** | `docs/**`, `README.md`, `.env.example`, `apps/web` README/env docs |
| **Forbidden** | Application logic in `apps/api/app` / `apps/worker` / `apps/web/src` |
| **Deliverables** | Runbook updates, env tables, Railway notes, glossary touch-ups, product grid doc sync |
| **Conflict risk** | **Low** |

### Captain / Integration Manager

| | |
|--|--|
| **Allowed** | Planning docs, ownership map, conflict scans, integration branch, merge reports |
| **Forbidden** | Uncontrolled feature coding, provider calls, production deploys without Steve |

---

## Conflict risk summary

| Pair | Risk | Mitigation |
|------|------|------------|
| A ↔ B | Schema / job output shape | Versioned internal DTO or OpenAPI fragment agreed first |
| A ↔ D | Ledger + AI run tables | D proposes migration; A consumes; single merge owner |
| B ↔ D | Where caps enforced | Enforce in B pre-call; persist decisions via A’s log model |
| C ↔ A | API fields | A stabilises read-only status contract before C ships |

---

## Merge order (see checklist)

F baseline → B mock + skeleton → E tests → A persistence → D policy → B modules → C UI → Beacon → E harden → F final.

---

## Exact Cursor prompts for Agent A–F *(copy when GO Phase 7B)*

**Agent A — API AI state**

```text
You are FeedFoundry Phase 7 Agent A (API). Branch: phase7/agent-a-api-ai-state from main.
Scope: models, schemas, migrations, routes, tests ONLY under apps/api for AI run/stage/output readiness and optional product output kinds. Do not edit apps/web or apps/worker. Do not add provider keys. Do not call external APIs. Coordinate JSON field names with docs/ai-operating-brief.md. Small migrations only; no unrelated refactors. Tests must use sqlite fixtures like existing tests.
```

**Agent B — Worker AI orchestrator**

```text
You are FeedFoundry Phase 7 Agent B (Worker). Branch: phase7/agent-b-worker-ai-orchestrator from main.
Scope: apps/worker only. Implement AIProvider interface, mock provider, Captain skeleton, transcript chunking utilities, module stubs (Producer, Visual, Product Signal, Verifier, Governor, Validator hooks). No real OpenAI/network in tests. No edits to apps/api or apps/web. Follow docs/ai-operating-brief.md contracts.
```

**Agent C — UI**

```text
You are FeedFoundry Phase 7 Agent C (Web). Branch: phase7/agent-c-ai-ui-product-grid from main.
Scope: apps/web/src and web env docs only. Display AI/job readiness from API when available; optional product grid UX as PREVIEW only—no promises of Shopify/Etsy. No provider keys. Use flat API errors. npm run lint && typecheck && build must pass.
```

**Agent D — Cost / storage**

```text
You are FeedFoundry Phase 7 Agent D (Cost/storage policy). Branch: phase7/agent-d-ai-cost-storage from main.
Scope: apps/api services, coordinated worker config helpers if needed, tests, .env.example placeholders. Do not rewrite unrelated billing. Document AI cost vs processing minutes; implement caps as config-driven stubs/interfaces until Steve approves ledger coupling. No UI edits.
```

**Agent E — Tests**

```text
You are FeedFoundry Phase 7 Agent E (Tests/evals). Branch: phase7/agent-e-ai-tests-evals from main.
Scope: tests and fixtures only (+ minimal test hooks if required with Captain approval). Mock provider, schema validation, malformed JSON, caps, cancellation, product-grid fixtures. No real secrets; no live providers.
```

**Agent F — Docs**

```text
You are FeedFoundry Phase 7 Agent F (Docs). Branch: phase7/agent-f-ai-docs-runbook from main.
Scope: docs/, README, .env.example, apps/web README/.env.example. Align runbook with Phase 7 env vars and service boundaries. No application logic changes.
```

---

## Stop condition

Parallel agents **must not** start until Steve: **GO Phase 7B**.
