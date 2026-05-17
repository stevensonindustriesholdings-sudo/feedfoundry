# YouTube creator-authorised ingest (soon path)

FeedFoundry **V1** remains **upload-only** (no arbitrary URL ingestion). A future **creator-authorised** YouTube lane could work as follows:

1. **OAuth / channel linkage** — creator proves channel ownership; scopes read metadata + **their** uploads only.
2. **Explicit asset selection** — pick video IDs from owned inventory; no trending/explore scraping.
3. **Download + normalize** — worker pulls authorised source into private object storage (same credit reservation model as uploads).
4. **Manifest** — `RenderJobSpecV1`-style metadata references `editorial_status: pending_review` until operator approval.

This path must remain **opt-in**, **audited**, and **separate** from public URL ingestion guardrails in product doctrine.
