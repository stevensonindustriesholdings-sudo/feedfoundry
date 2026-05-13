# Glossary

| Term | Meaning |
|------|---------|
| **API** | FastAPI service in `apps/api`; OpenAPI at `/openapi.json`. |
| **Annual access** | Entitlement to hosted archive/manifest for a yearly period; not framed as monthly MRR SaaS. |
| **Base44** | Intended customer UI layer: dashboard, uploads, billing UX; calls this repo’s API with server-side secrets. |
| **FF** | FeedFoundry prefix (e.g. `FF_INTERNAL_API_KEY`, idempotency keys `ff:…`). |
| **Hosted manifest** | Public or semi-public JSON describing an asset for humans and AI agents. |
| **Job** | One processing run from a single uploaded `media_asset` through pipeline stages. |
| **Ledger (internal)** | Wallet fields and transactions: reserve before work, debit on success, release on failure or for unused reservation. Customer copy: **processing allowance**, not “credits.” |
| **Organisation** | Billing and access boundary; owns wallet and media. |
| **Presign** | Short-lived signed URL for direct browser-to-object-storage upload. |
| **Processing allowance** | Customer-facing name for what the ledger meters (included with annual access + optional add-ons). |
| **Provider** | LLM or speech vendor (OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, local/OSS) behind the worker abstraction. |
| **R2** | Cloudflare R2 or S3-compatible object storage for sources and outputs. |
| **Worker** | `apps/worker` polling process: FFmpeg pipeline, AI modules, writes outputs. |
