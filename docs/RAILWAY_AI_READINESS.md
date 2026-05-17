# Railway AI readiness (staging checklist)

**Scope:** `api-v2-IQho` + `worker-v2` on Railway — **readiness notes only** (no env mutations from this doc).

| Area | Readiness note |
|------|-----------------|
| Secrets | `OPENAI_*`, `FF_AI_*` mirrors documented in `.env.example`; never expose to browser. |
| AI router | `ai-routing.yaml` + env `model_env` resolution; failures must be structured JSON. |
| Worker | FFmpeg binaries on PATH; AI modules must stay **mock-safe** until budgets explicitly enabled. |
| CEO package alignment | Optional: mirror `FF_AI_PROVIDER` / `FF_AI_OPENROUTER_ENABLED` with CEO `si-ai-routing` README table. |
| Cost | Jobs must **estimate → reserve → debit** processing minutes per existing ledger rules — unchanged. |

Before enabling any live LLM provider in staging, run API `pytest` for router + ledger tests and a single controlled job smoke.
