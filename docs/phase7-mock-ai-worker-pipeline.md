# Phase 7 — mock AI enrichment in the worker (ops trail)

This document describes the **optional** worker-side mock AI pipeline that persists internal
`AIRun` and `AIStageLog` rows. It is **not** customer-facing output storage and does **not**
change processing-minute reserve/debit policy or the credit ledger.

## Feature flag

| Variable | Default | Purpose |
|----------|---------|---------|
| `FF_WORKER_AI_ENRICHMENT_ENABLED` | **false** (unset) | When truthy, the worker runs structured-AI enrichment stages after outputs are written and persists `AIRun` / `AIStageLog`. |
| `FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE` | **false** | With `AI_STRUCTURED_PROVIDER_MODE=canary_openai` and full canary gates, allows bounded OpenAI HTTP for **transcript_intelligence** only (visual/product remain mock). |
| `FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS` | `4` | Max OpenAI `complete()` calls per enrichment run for transcript intelligence before falling back to mock (default covers one chunk × four schemas). |

Legacy name `FF_WORKER_MOCK_AI_ENRICHMENT` is **not** used; configure only
`FF_WORKER_AI_ENRICHMENT_ENABLED`.

## Provider policy

- **Default:** `MockAIProvider` only (deterministic JSON, **no network**, no provider SDK calls
  from this path).
- **Bounded OpenAI (transcript only):** when `FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE=true`,
  `AI_STRUCTURED_PROVIDER_MODE=canary_openai`, and all structured canary gates pass (see
  [phase7-openai-canary.md](./phase7-openai-canary.md)), transcript intelligence uses
  `OpenAIStructuredProviderShell` for the first *N* completions (`FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS`),
  then mock for the remainder. Visual analysis and product signal stay on mock regardless.
- **Legacy:** `AI_ENABLE_MOCK_PROVIDER` still maps to `mock`/`disabled` when structured mode is unset.

## Persistence (`AIRun` / `AIStageLog`)

- **`AIRun`:** one logical enrichment attempt per job run when the flag is on and there is at
  least one actionable input (transcript text and/or optional visual inputs and/or product
  images). Tracks coarse status (`running`, `completed`, `failed`, `cancelled`).
- **`AIStageLog`:** one row per high-level stage (`transcript_intelligence`, `visual_analysis`,
  `product_signal`) with provider/model, token tallies, internal cost estimate fields, and
  validation outcome. **Skipped** stages are logged when inputs are absent (e.g. no keyframes
  for visual, no `product_images` for product signal).

Internal `cost_estimate_internal` on stage logs is **not** customer processing minutes. Customer
allowance remains on `Job` and the wallet / ledger paths unchanged by this feature.

## Inputs and skips

- **Transcript:** runs when segment text can be joined from the transcript payload; otherwise the
  transcript stage is **skipped** (no synthetic chunk_plan–only visual run).
- **Visual analysis:** runs only when `media_inspection` JSON includes at least one of:
  non-empty `keyframes`, `ocr_snippets`, or `product_images` (structured lists). `chunk_plan`
  alone does **not** trigger visual analysis.
- **Product signal:** runs only when `product_images` is a non-empty list of objects with
  `product_image_id`.

## Cancellation

Between stages the worker reloads `Job` from the database; if the job is **`CANCELLED`**, the
pipeline marks the `AIRun` as cancelled and stops without running later stages.

## Validation

Outputs pass through `OutputValidator` (Pydantic contracts). Validation failures produce
`AIStageLog` rows with `status=failed` and do not promote payloads to customer-visible storage
through this path.

## Tests

See `apps/worker/tests/test_mock_ai_pipeline_integration.py` (worker pytest with
`PYTHONPATH=../api:.`). Agent E branch documents merge from Agent B when tests depend on
`ai.pipeline` modules.
