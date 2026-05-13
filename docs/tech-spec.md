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

## Job state machine

Linear happy path:

`created` → `estimating` → `awaiting_credit_reservation` → `queued` → `probing` → `extracting_audio` → `chunking` → `transcribing` → `generating_outputs` → `qa_validating` → `exporting` → `complete`.

Failure: any active state → `failed`.

Cancellation: `created`, `queued`, or `awaiting_credit_reservation` → `cancelled`.

## Internal ledger (processing allowance)

Operations: estimate, reserve, debit, release, refund per `credit_transactions` types. The wallet maintains `balance_available`, `balance_reserved`, and lifetime counters. **Failed jobs:** the worker releases the full reservation (`fail_job` + `ledger_release_failure_key`); no debit, so the customer’s allowance is not consumed for that failure. Expose balances in product UI as **processing allowance**, not “credits.”

## AI

All model identifiers come from environment variables. Runtime policy is defined in `ai-routing.yaml`. Provider implementations live under `apps/worker/providers/`. Usage is logged to `ai_usage_logs`.

## Public manifest

`GET /v1/manifests/{creator_slug}/{asset_slug}.json` serves (or redirects to) hosted manifest JSON derived from `job_outputs` where `output_type = hosted_manifest`.
