# FeedFoundry MVP v0.1 — Parallel Agent Contract

**Status:** coordination document. **Not** a feature spec for implementation in this commit.

Every parallel agent must **read this file first**, keep changes narrow, **list changed files** in handoffs, add tests/smoke where practical, and **not invent unrelated platform features**.

**Control rod (put at the top of every lane agent prompt):**

> Do not invent extra product scope. Do not generalise the platform. Do not redesign unrelated systems. The only accepted work is the named lane. If you find unrelated issues, write them in a TODO section and keep moving.

---

## Locked scope (MVP v0.1)

- Customer buys **annual access** plus **media processing time** in **minutes/hours**.
- **No** customer-facing credits.
- **No** AI-token exposure to customers.
- **No** fake currency.
- **No** multi-provider routing in MVP.
- **No** public marketplace.
- **No** team roles.
- **No** external platform import.
- **Core flow:** access → processing time → upload → process → outputs.

---

## Customer-facing language (required)

Use: **processing time**, **processing minutes**, **processing hours**, **hours remaining**, **minutes remaining**, **currently processing**, **processing top-up**.

---

## Forbidden customer-facing language

**credits**, **AI credits**, **tokens**, **usage units**, **coin** / **currency** / **points** (and close variants). Dashboard and customer APIs must not surface these terms.

---

## Processing-time rules (product)

1. Deduct processing minutes **only after** a job **completes successfully**.
2. **Failed** jobs **release** reserved minutes and **charge zero**.
3. **Active** jobs may **reserve** estimated minutes internally.
4. If upload is **slightly** over remaining processing time, allow **goodwill overage**.
5. **MVP goodwill:** allow when `shortfall_minutes <= FF_GOODWILL_MAX_SHORTFALL_MINUTES` (default **5**).
6. If shortfall is **larger**, block with **`INSUFFICIENT_PROCESSING_TIME`**.
7. Dashboard must **never** show the word **credits**.

---

## Shared API / error names

Use consistently across API and clients:

| Name | Typical use |
|------|-------------|
| `ACCESS_INACTIVE` | Annual access not valid |
| `INSUFFICIENT_PROCESSING_TIME` | Blocked job; not enough minutes even after goodwill |
| `PROCESSING_TIME_RESERVATION_FAILED` | Could not reserve minutes |
| `MEDIA_DURATION_TOO_LONG` | Media exceeds max duration |
| `JOB_FAILED_PROCESSING_RELEASED` | Job failed; reserved time released |

---

## Shared environment variables

Document and align implementations to these names (values are examples unless noted):

| Variable | Notes |
|----------|--------|
| `FF_GOODWILL_MAX_SHORTFALL_MINUTES` | Default **5** |
| `FF_MAX_MEDIA_SECONDS` | e.g. **7200** |
| `FF_AI_ENABLED` | e.g. **true** |
| `FF_MAX_TOKENS_PER_JOB` | e.g. **120000** |
| `FF_MAX_COST_PER_JOB_GBP` | e.g. **2.00** |
| `FF_RETRY_MAX` | e.g. **2** |

Optional (Agent B): `FF_GOODWILL_MAX_MINUTES_PER_ACCOUNT_PER_YEAR` — implement when quick; else TODO + config stub.

Stripe and auth env vars are defined in lanes **C** and **A**; this table is the **cross-lane** processing/AI cap set.

---

## Parallel lanes (ownership)

| Agent | Lane | Owns | Must not touch |
|-------|------|------|----------------|
| **A** | Auth / account ownership | Users, accounts, ownership on uploads/jobs/outputs, account-scoped queries | Stripe, dashboard styling, AI model logic |
| **B** | Processing-time ledger | Minutes accounting, goodwill, reserve/consume/release, usage API messages | Stripe Checkout, UI styling, auth design |
| **C** | Stripe | Checkout Sessions, webhooks, annual access, processing-hour top-ups | Pipeline, dashboard redesign |
| **D** | Customer dashboard | Upload, jobs, outputs, hours remaining UI | Backend schema except typed API assumptions |
| **E** | Admin ops | Internal tables/actions, manual grant, retry/cancel | Customer-facing UI polish |
| **F** | Railway / AI controls | Env validation, kill switch, caps, logging, deployment docs | Billing terminology, Stripe, customer UI |
| **G** | Integration captain | Merge/reconcile branches after A–F | New feature invention |

**Core sequencing:** **A** and **B** are core. **C, D, E, F** may run in parallel but must code against this contract. **G** merges and resolves.

Suggested merge order after A/B land: **A → B → F → C → D → E** (adjust if conflicts dictate; G owns final order).

**Branches / worktrees (suggested):**

- `agent/auth-account-ownership` — A  
- `agent/processing-time-ledger` — B  
- `agent/stripe-access-processing-time` — C  
- `agent/customer-dashboard-mvp` — D  
- `agent/admin-ops-mvp` — E  
- `agent/railway-ai-controls` — F  
- `agent/integration-mvp-v01` — G  

Use **isolated worktrees** per lane so agents do not trample each other.

---

## Run order (operations)

| Step | Action |
|------|--------|
| 1 | Commit this contract + Cursor rule on **main** (coordination-only). |
| 2 | Launch Agents **A–F** in separate worktrees / background agents. |
| 3 | Prefer **A** and **B** finishing first when possible. |
| 4 | Merge **A → B → F → C → D → E** (G adjusts). |
| 5 | Run **G** integration branch. |
| 6 | Smoke test. |
| 7 | Ship private pilot. |

---

## Agent handoff checklist

Each lane agent ends with:

1. **Changed files** (exact list).  
2. **Migrations** (if any).  
3. **Exact test commands** run or to run.  
4. **Integration points** for other agents (APIs, function names, env vars).

---

## Reference: goodwill / block payloads (API shapes)

**Small shortfall allowed (goodwill):**

```json
{
  "allowed": true,
  "warning": true,
  "message": "You are a little short on processing time. We will cover the extra X minutes this time so your file can be processed.",
  "available_minutes": 3,
  "estimated_minutes": 5,
  "goodwill_minutes": 2
}
```

**Large shortfall blocked:**

```json
{
  "allowed": false,
  "error": "INSUFFICIENT_PROCESSING_TIME",
  "message": "This file needs about X minutes of processing time, but you only have Y minutes remaining. Please top up before starting this job.",
  "available_minutes": 3,
  "estimated_minutes": 42,
  "shortfall_minutes": 39
}
```

---

## Launching parallel agents

1. Ensure **Step 1** (this doc + `.cursor/rules/feedfoundry-mvp.mdc`) is on **main**.  
2. Open **one worktree per lane** (or Cloud Agent per lane).  
3. Paste the **control rod** at the top of each agent prompt, then the lane-specific brief.  
4. Instruct each agent to read **`docs/MVP_PARALLEL_CONTRACT.md`** and **`.cursor/rules/feedfoundry-mvp.mdc`**.
