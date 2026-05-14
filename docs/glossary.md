# Glossary

| Term | Meaning |
|------|---------|
| **AI provider fallback** | When the primary LLM/speech vendor errors, hits a budget cap, or is unavailable, the worker’s AI router retries or switches to the **fallback** provider/model defined for that module in `ai-routing.yaml`. |
| **API** | FastAPI service in `apps/api`; OpenAPI at `/openapi.json`. |
| **Annual access** | Entitlement to hosted archive/manifest for a yearly period; not framed as monthly MRR SaaS. |
| **Base44** | Intended customer UI layer: dashboard, uploads, billing UX; calls this repo’s API with server-side secrets. |
| **Deprecated compatibility alias** | A route or JSON field kept for older clients (e.g. **`GET /v1/account/credits`**, **`*_credits`** on job/account payloads) that mirrors the canonical **processing-minute** fields — not the customer-facing product model. |
| **FF** | FeedFoundry prefix (e.g. `FF_INTERNAL_API_KEY`, idempotency keys `ff:…`). |
| **FFmpeg** | Media demux/decode/transcode toolchain used in the worker pipeline (`ffmpeg` / `ffprobe` binaries). |
| **Hosted manifest** | Public JSON describing an asset/episode for humans and agents (`hosted_manifest` output); often fetched without auth under `/v1/manifests/...`. |
| **Job** | One processing run from a single uploaded `media_asset` through pipeline stages. |
| **Job states (`uploaded`, `queued`, `processing`, `completed`, `failed`, `cancelled`)** | Customer-visible lifecycle on the `jobs` row. Only **`completed`** settles **actual processing minutes charged** toward allowance; **`failed`** and **`cancelled`** release reservations and do not consume completed allowance. |
| **Ledger (internal)** | Wallet fields and `credit_transactions`: reserve before work, debit on **completed** success, release on **failure** or **cancel** or for unused reservation. Customer copy: **processing allowance** / **minutes**, not “credits.” |
| **Organisation** | Billing and access boundary; owns wallet and media. |
| **Presign** | Short-lived signed URL for direct browser-to-object-storage upload. |
| **Processing allowance** | Customer-facing name for included **processing minutes** / **processing hours** with annual access plus optional add-ons. |
| **Processing minutes / processing hours** | Whole **minutes** are the ledger unit; **hours** are a derived display helper (e.g. on account/job responses). |
| **Provider** | LLM or speech vendor (OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, local/OSS) behind the worker abstraction. |
| **R2** | Cloudflare R2 or S3-compatible object storage for sources and outputs. |
| **Rate limit / retry / backoff** | Per `ai-routing.yaml`: bounded retries, exponential **backoff** with optional jitter, timeouts, and honouring provider **rate limit** headers when logged. |
| **Worker** | `apps/worker` polling process: FFmpeg pipeline, AI modules, writes outputs. |
