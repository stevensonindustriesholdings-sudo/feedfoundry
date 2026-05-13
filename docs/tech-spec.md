# FeedFoundry technical specification

## Overview

FeedFoundry processes creator-uploaded media into structured archive assets. V1 does not fetch media from arbitrary URLs.

## Components

| Component | Role |
|-----------|------|
| Base44 | Customer UI, auth UX, payments UX, proxies to Railway API |
| FastAPI (`apps/api`) | Presigned uploads, jobs, ledger/account balance, outputs, Stripe webhooks, admin |
| Worker (`apps/worker`) | FFmpeg, chunking, transcription orchestration, AI modules, QA, export |
| Postgres | Source of truth for orgs, wallets, jobs, outputs, usage logs |
| Object storage | Source files, intermediates, artifacts, public manifest |

## Job lifecycle (customer-visible states)

Jobs surface these **`JobStatus`** values: **`uploaded`**, **`queued`**, **`processing`**, **`completed`**, **`failed`**, **`cancelled`**.

- **`uploaded`**: job row exists; upload may still need **`POST /v1/uploads/complete`** before queueing.
- **`queued`**, **`processing`**: worker may run pipeline stages tracked separately in **`current_stage`** / **`progress_percent`**.
- **`completed`**: success; **`actual_processing_minutes_charged`** reflects settled usage; unused reservation is released.
- **`failed`**, **`cancelled`**: **do not consume** the customer’s processing allowance for charged minutes — reservations are released and nothing is debited as completed usage.

Cancellation is **`POST /v1/jobs/{job_id}/cancel`** for eligible in-flight states; idempotent if already terminal.

## HTTP errors (canonical)

All API errors share a **flat** JSON body:

```json
{"code": "machine_readable_code", "message": "Human-readable message.", "fields": []}
```

## Wallet / processing allowance (internal ledger)

The **`credit_wallets`** row (historical table name) stores whole **processing minutes**:

- **`processing_minutes_available`** — balance not reserved.
- **`processing_minutes_reserved`** — held against active jobs.
- **`processing_minutes_spent_lifetime`** — settled completed usage (DB column).

**`GET /v1/account`** (and **`GET /v1/account/usage`**) return **`processing_minutes_available`**, **`processing_minutes_reserved`**, **`processing_minutes_used_lifetime`** (same lifetime counter as the DB field, JSON naming), plus **`processing_hours_available`** as a display helper.

**`GET /v1/account/credits`** is a **deprecated compatibility alias** only — same payload; do not describe “credits” as the customer model.

Some responses still include **`*_credits` optional fields** — deprecated compatibility aliases mirroring the canonical **`*_processing_minutes`** fields.

Operations follow **estimate → reserve → debit / release** on **`credit_transactions`**. Active jobs may **reserve estimated processing minutes**; **failed** and **cancelled** jobs **must not** debit **`actual_processing_minutes_charged`** for allowance consumption.

## Job model (selected fields)

| Field | Role |
|-------|------|
| **`media_kind`** | Normalized media type for the job |
| **`source_content_type`** | Observed content type from processing |
| **`upload_content_type`** | Declared upload MIME where recorded on the asset |
| **`estimated_processing_minutes`** | Pre-run estimate |
| **`reserved_processing_minutes`** | Ledger hold while active |
| **`actual_processing_minutes_charged`** | Settled minutes after **completed** |

## AI

All model identifiers come from environment variables. Runtime policy is defined in `ai-routing.yaml`. Provider implementations live under `apps/worker/providers/`. Usage is logged to `ai_usage_logs`.

## Public manifest

`GET /v1/manifests/{creator_slug}/{asset_slug}.json` serves (or redirects to) hosted manifest JSON derived from `job_outputs` where `output_type = hosted_manifest`.
