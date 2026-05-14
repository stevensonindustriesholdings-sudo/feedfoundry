# Phase 7 — Implementation checklist

**Gates:** Do not start **Phase 7B** (parallel Cursor agents) or **Phase 7C** (code) until Steve says **GO**. Doc-only work is **Phase 7A**.

---

## Phase 7A — Docs & planning (Captain)

- [ ] `docs/ai-operating-brief.md` reviewed
- [ ] `docs/phase7-agent-ownership-map.md` reviewed
- [ ] `docs/phase7-product-grid-extension.md` reviewed
- [ ] `docs/phase7-railway-storage-provider-architecture.md` reviewed
- [ ] This checklist reviewed
- [ ] Design decisions logged (AI cost vs processing minutes; partial failure matrix; customer-visible vs admin metrics)
- [ ] Commit docs on a branch (e.g. `phase7/captain-ai-operating-brief`) after Steve **GO Phase 7A**

---

## Merge / build order (recommended)

0. **Captain** — docs only (this set).
1. **Agent F** — env/runbook baseline so all lanes share contracts.
2. **Agent B** — worker provider abstraction + **mock provider** (no real calls in tests).
3. **Agent E** — fixtures + schema + mock tests before heavy logic.
4. **Agent A** — API models/routes/migrations for AI run/stage/output readiness (+ product output slots if in scope).
5. **Agent D** — caps, rate limits, storage policy hooks, cost/routing log models (interfaces first).
6. **Agent B** — transcript intelligence module(s) behind flags.
7. **Agent B** — visual + **product signal** modules behind `AI_VISUAL_ANALYSIS_ENABLED` / `AI_PRODUCT_GRID_ENABLED`.
8. **Agent B** — Verifier, Governor, Output Validator pipeline.
9. **Agent C** — UI for AI status / output readiness / optional product preview (no false promises).
10. **Agent B** — Repository Beacon behind `AI_REPOSITORY_BEACON_ENABLED`.
11. **Agent E** — test/eval hardening.
12. **Agent F** — final docs/runbook alignment.

---

## Per-lane exit criteria (high level)

| Lane | Exit |
|------|------|
| F | Env table + runbook + no secrets in examples |
| B | Mock provider passes; Captain skeleton calls no real API in CI |
| E | Golden fixtures; malformed JSON; cap; cancel tests green |
| A | Migrations reviewed; OpenAPI/internal contract stable for worker |
| D | Caps enforced in code path or documented stubs with tests |
| C | Lint/typecheck/build; no keys in client; copy matches product doctrine |

---

## Accounting / pricing (decide before ledger code changes)

- [ ] Does successful AI enrichment affect **`actual_processing_minutes_charged`**?
- [ ] Is AI API cost **v1 internal only** vs customer-visible allowance?
- [ ] Are optional AI stages **plan-gated** (config/DB, not hardcoded Stripe)?
- [ ] **Cancellation:** in-flight AI calls + internal cost handling documented.
- [ ] **Customer-visible** vs **admin-only** metrics for AI runs.

**Rule:** No billing/Stripe product hardcoding in business logic — config/DB for plan changes.

---

## Risk register (check during each merge)

- AI cost runaway  
- Transcript chunking / merge failure  
- Malformed JSON from providers  
- Hallucinated facts / unsupported claims  
- Weak visual analysis  
- **Product-grid hallucinations; invented prices/offers/availability**  
- Provider rate limits / outages  
- Jobs stuck in `processing`  
- Cancellation not interrupting AI work  
- Secrets mishandling  
- **Railway / storage lock-in**  
- OpenAI-only coupling (adapter bypassed)  
- Customer-visible slop  
- Fake GEO / spam  
- Overbuilding autonomous agents too early  
- **“Credits” / “AI tokens” leaking to customer UI**  
- **UI promising Shopify/Etsy/product sync before backend exists**

---

## Freeze / checkpoint protocol

- Before each agent merge: **checkpoint commit** on agent branch; Captain runs conflict scan on `main..agent`.
- **Emergency freeze:** no merge, no push, no provider calls; report-only inventory.
- After integration merge to `main`: API + worker + web checks per runbook.

---

## Explicit stop

**Do not** call OpenAI or any provider; **do not** deploy Railway; **do not** push without Steve; **do not** start Phase 7C until **GO Phase 7C**.
