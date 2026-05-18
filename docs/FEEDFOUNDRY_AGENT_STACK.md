# FeedFoundry Agent Stack — v0.1 (Hermes-oriented)

This document defines the **15-agent** processing team for FeedFoundry’s creator-archive pipeline. Roles are **logical** (Hermes-style decomposition); v0.1 code implements them as **deterministic, rule-based** Python modules with **no live OpenAI/OpenRouter** calls. Provider routing in production remains the existing **AI router**; this stack is a **bundle contract** for structured outputs, QA gates, and auxiliary classifiers.

## Design principles

1. **Evidence-grounded**: every artefact cites `derived_from` / span hints where applicable; no invented URLs, prices, or partner claims.
2. **Swappable providers**: agents consume `FeedFoundryJobInput`; generation is stubbed or template-driven until wired to the router.
3. **Mocks explicit**: any synthetic content is labelled `execution_mode="deterministic_mock"` in bundle metadata.
4. **No URL ingestion (V1)**: repository manifest agents reason over **hosted manifest fields and repo-local names**, not external crawling.
5. **GEO is gated**: see `docs/GEO_FRESHNESS_AGENT.md` (`FF_GEO_FRESHNESS_LIVE_RESEARCH_ENABLED` defaults false; **no web** on the customer path in v0.1).

## The fifteen agents

| # | Agent id | Responsibility | Primary outputs |
|---|-----------|----------------|-----------------|
| 1 | `captain` | Scope, ordering, shared context normalization | Bundle envelope, run manifest |
| 2 | `transcript_steward` | Raw transcript hygiene, segment sanity | `raw_transcript` notes |
| 3 | `clean_transcript_editor` | Disfluency collapse, reading-order clean text | `clean_transcript` |
| 4 | `chapter_architect` | Timestamped chapters from transcript + duration | `chapters` |
| 5 | `clip_scout` | Clip candidate windows with rationale | `clip_candidates` |
| 6 | `show_notes_writer` | Episode show notes (structured) | `show_notes` |
| 7 | `metadata_curator` | Cross-surface metadata (podcast/video fields) | `metadata` |
| 8 | `cta_designer` | Archive CTAs (intents, no secret URLs) | `ctas` |
| 9 | `fact_sheet_analyst` | Extractive fact sheet lines | `fact_sheet` |
| 10 | `faq_author` | FAQs grounded in transcript | `faqs` |
| 11 | `hosted_manifest_composer` | Curates **hosted manifest JSON** fields (summary, slugs, outputs list) | `hosted_manifest_hints` |
| 12 | `export_bundle_assembler` | Export bundle index shape / artefact checklist | `export_bundle_hints` |
| 13 | `repository_manifest_librarian` | **`llms.txt` / `llms-full.txt` candidates** + doc priorities | `repository_manifest` |
| 14 | `schema_org_specialist` | JSON-LD skeleton (`PodcastEpisode`/`VideoObject`-style) | `schema_org` |
| 15 | `verifier` | Schema + policy checks across sub-outputs | `verification` |

**Arbitration (Hermes pattern):** a **Judge** step (`judge` in code) is **not** a sixteenth agent; it consumes `verification` and producer drafts to emit a **deterministic verdict** (`pass` / `pass_with_notes` / `blocked`). It ships in the same bundle as agent #15’s downstream step.

### Auxiliary (non-counted) specialists

- **FFmpeg failure classifier** — maps stderr/return-code patterns to a **failure_family**; always returns `debit_processing_minutes: false` (policy signal only; ledger unchanged in classifier).
- **GEO freshness** — gated; default **static fixture** path (`docs/GEO_FRESHNESS_AGENT.md`).

## Bundle I/O

- **Input:** `FeedFoundryJobInput` (`ai/feedfoundry_agents/schemas.py`).
- **Output:** `FeedFoundryAgentBundleOutput` from `run_feedfoundry_agent_bundle(...)`.
- **Orchestrator:** `ai/feedfoundry_agents/orchestrator.py` — single entrypoint, **deterministic** ordering.

## Integration stance (v0.1)

- **Worker:** optional hook after transcript + FFmpeg-derived inspection and the main JSON output pass (same `_write_stub_outputs` transaction as manifest/export index). Enable with **`FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED`** (`1` / `true` / `yes`; **default off**). When off, behaviour matches the pre-wire worker. When on, the worker writes **`agent_bundle.json`** (`JobOutputType.AGENT_BUNDLE`) via `run_feedfoundry_agent_bundle` before processing minutes are settled; bundle failures raise `agent_bundle_failed` and **do not debit** reserved minutes (settlement runs only after a successful output pass).
- **Hosted manifest truth:** `hosted_manifest.json` **`outputs_available`** (and optional **`artifacts.agent_bundle`**) list **`agent_bundle`** only after **`agent_bundle.json`** is **successfully uploaded** and the `job_outputs` row exists — not merely because the bundle feature flag is enabled. If the bundle step is skipped (no transcript segments) or fails before upload, the public manifest does not advertise the bundle.
- **API (operator, optional):** `GET /v1/admin/jobs/{job_id}/agent-bundle` returns parsed JSON from object storage when **`FF_AGENT_BUNDLE_ADMIN_API_ENABLED`** is truthy **and** `FF_INTERNAL_API_KEY` auth is valid (same internal-key pattern as other `/v1/admin/*` routes). Returns **404** when the flag is off, the row is missing, or the blob is absent. No customer-facing route; no ledger changes.
- **Tests:** contract tests lock JSON shape for CI.

## Hermes / local agent development

For AI agent work **in this repository**, prefer **native Hermes ACP** (`hermes acp`) and CEO automation scripts under **`stevenson-skunkworks-ceo`** when that repo is present on the machine — so Hermes skill iteration and ACP tooling stay aligned. This is a **local developer convenience** only; **CI does not require Hermes**.

## Versioning

- `schema_version`: `"0.1"` on all top-level agent payloads until first breaking change.
