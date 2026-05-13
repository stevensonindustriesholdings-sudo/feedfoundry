# Processing time product scope

## Decision

FeedFoundry bills and communicates in **processing minutes / hours**, not abstract “credits” or customer-facing AI tokens. The wallet (`credit_wallets`) stores integer **processing minutes**: `balance_available`, `balance_reserved`, and `balance_spent_lifetime` (used on successful job completion).

When we revisit billing, consider: renaming DB tables/columns from `credit_*` to `processing_*`, aligning Stripe metadata copy with “processing top-up”, and reconciling annual “included credits” in Stripe settings with explicit “included processing minutes” naming.

## Goodwill overage

On job creation, the API estimates **processing minutes** for the upload (from probed media duration when present; otherwise a routing-based fallback).

1. If `available >= estimated`: reserve `estimated`; no goodwill.
2. If `available < estimated`: `shortfall = estimated - available`.
3. If `shortfall <= FF_GOODWILL_MAX_SHORTFALL_MINUTES` (default **5**): allow, grant exactly `shortfall` goodwill minutes, then reserve the full `estimated`.
4. Else: block with `INSUFFICIENT_PROCESSING_TIME` and a message including minutes needed vs remaining.

**Annual cap:** `FF_GOODWILL_MAX_MINUTES_PER_ACCOUNT_PER_YEAR` (default **30**) is enforced against goodwill grants in the **UTC calendar year** (see `TODO` in code to move to subscription anniversary when billing hardens).

## Settlement

- **Reserve** when the job is accepted (queued): minutes move from available → reserved (`processing_minutes_reserved` ledger memo).
- **Success:** debit from reserved into spent lifetime (`processing_minutes_used`); release any unused remainder of the reserve (`processing_minutes_released`).
- **Failure:** release the full reserve back to available (`processing_minutes_released`). If goodwill had been granted for that job, revoke it from available (`GOODWILL_REVOKE` / `goodwill_processing_minutes_revoked_job_failed`) so failed runs do not retain free goodwill balance.
- Goodwill is only granted when the job is **allowed to start** (same transaction as reserve).

## Internal ledger memos / types

| Concept | Transaction type | Memo (where applicable) |
|--------|------------------|-------------------------|
| Purchases, annual grants, admin grants | `PURCHASE`, `ANNUAL_GRANT`, `ADMIN_ADJUSTMENT` | `processing_minutes_granted` |
| Goodwill | `GOODWILL_GRANT` | `goodwill_processing_minutes_granted` |
| Goodwill reversal on failed job | `GOODWILL_REVOKE` | `goodwill_processing_minutes_revoked_job_failed` |
| Reserve / debit / release | `RESERVE`, `DEBIT`, `RELEASE` | `processing_minutes_reserved`, `processing_minutes_used`, `processing_minutes_released` |

## API shapes (job creation)

**Allowed (no warning):** normal `200` with `allowed: true`, `warning: false`, `estimated_minutes`, `reserved_credits` / `estimated_credits` (legacy mirrors, same integer as minutes).

**Allowed with goodwill shortfall:**

```json
{
  "allowed": true,
  "warning": true,
  "message": "We covered X extra minutes for this upload.",
  "available_minutes": 3,
  "estimated_minutes": 5,
  "goodwill_minutes": 2
}
```

**Blocked:**

```json
{
  "allowed": false,
  "error": "INSUFFICIENT_PROCESSING_TIME",
  "message": "…",
  "available_minutes": 3,
  "estimated_minutes": 12,
  "shortfall_minutes": 9
}
```

HTTP status for blocked: **400** with the object as FastAPI `detail`.

## Admin

- `GET /v1/admin/organisations/{organisation_id}/processing` — balances, goodwill YTD, recent ledger rows.
- `POST /v1/admin/organisations/{organisation_id}/grant-processing-minutes` — body `{ "minutes": N, "memo": "optional" }`.

## Customer dashboard copy

Use strings such as: **processing time remaining**, **hours/minutes remaining**, **currently processing** (when reserved &gt; 0), **processing top-up**, and goodwill: **“We covered X extra minutes for this upload.”** Do not surface “credits” or “AI tokens” on the customer dashboard.
