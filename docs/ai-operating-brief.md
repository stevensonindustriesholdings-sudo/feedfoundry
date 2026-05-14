# FeedFoundry AI Operating Brief

**Status:** Phase 7 planning — production AI modules (worker) vs Cursor build agents are **different concepts**; see `docs/phase7-agent-ownership-map.md`.

**Baseline:** `main` after PR #3 merge (integration spine: processing minutes, flat errors, cancel, web, tests, docs).

---

## 1. Terminology

| Term | Meaning |
|------|---------|
| **Cursor build agent** | Temporary parallel coding workstream (branch/worktree), controlled by Captain. |
| **FeedFoundry AI module** | Deterministic worker-side logical unit with strict JSON contracts, budgets, and tests. May become more agentic later. |

---

## 2. Product objective (Phase 7)

FeedFoundry does **not** “call OpenAI and summarise.” The **AI Worker Intelligence Layer** turns **transcripts, media metadata, thumbnails, keyframes, OCR, visual cues, existing outputs**, and **optional product grid / product imagery context** into **structured, validated, auditable** creator/archive intelligence.

**Target assets:** factsheets, FAQs, chapters, metadata, CTAs, Hosted Manifest enrichment, GEO/chat/search-ready knowledge objects, visual analysis reports, **product signal reports**, **product-to-content associations**, output quality reports, confidence/caveat notes, archive freshness signals, repository update recommendations.

**Launch wedge:** video / audio / podcast upload → transcript intelligence → Hosted Manifest / AI-readable archive outputs. **Product Grid** is an **extension path**, not a pivot — no full ecommerce, no Shopify/Etsy sync unless explicitly approved.

**Non-goals (v1):** autonomous web browsing; unbounded agent loops; customer-visible prose without schema validation; fake GEO; keyword spam; provider keys in browser; uncontrolled AI spend; hard OpenAI-only coupling; Railway lock-in; scraping external shops without allow-listed connectors.

---

## 3. Logical modules (v1 = deterministic worker modules)

### 3.1 Captain / Orchestrator

**Owns:** per-job **AI execution plan** (bounded DAG or ordered stages), module selection, retry/fail/partial decisions, **budget enforcement**.

**Responsibilities:** Build plan from job type, media kind, transcript availability, visual assets, **product imagery flags**, org tier, feature flags. Select modules: Transcript Intelligence, Visual Analyst, **Product Signal Extractor**, Verifier, Editor/Governor, Repository Beacon (subject to flags). Enforce cost/token ceilings, timeouts, retries, provider fallback, **cancellation checks between chunks/stages**, output validation gates.

**Decisions:** complete | partial complete | retry stage | fail stage | fail job | log support/product-intelligence signal.

**Hard rules:** no free-running loops; **every LLM call is named, budgeted, schema-bound, and logged**; no provider call without pre-flight cost/risk check; **no customer-visible output** before Validator + Governor.

---

### 3.2 Producer / Transcript Intelligence Agent

**Owns:** transcript-derived structured knowledge.

**Extract:** factual claims; answerable facts; named entities; people; organisations; locations; tools/products/resources; questions answered; audience intent; buyer/search intent; GEO/chat/search intent; authority signals; instructions/steps; advice/recommendations; caveats/disclaimers; controversial/unsupported claims; CTA opportunities; metadata/tag opportunities; chapter boundaries; summary hierarchy; evergreen vs time-sensitive signals.

**Must:** transcript **chunking** with overlap; **timecode/segment provenance**; **strict JSON**; never store loose prose as final artifact; avoid unsupported claims (Verifier catches remainder).

---

### 3.3 Visual Analyst

**Owns:** thumbnails, keyframes, scene-change cues, OCR/title cards, screenshots, diagrams, charts, **product visuals**, visible on-screen metadata.

**Extract:** thumbnail/keyframe descriptions; OCR text; visible entities; visual product/tool/resource cues; chart/diagram/screenshot classification; scene boundaries; visual tags; **mismatch flags** (title vs transcript vs visuals); **confidence per item**; evidence links to frame/timestamp where possible.

**Hard rules:** no unsupported identity claims; no hallucinated packaging/product text; no visual certainty beyond evidence; uncertain → labelled uncertain.

---

### 3.4 Product Signal Extractor / Product Grid Module *(Phase 7 extension)*

**Positioning:** Optional / preview support alongside video/audio wedge. CSV/API import = **coming soon** unless built. No checkout; no full Shopify/Etsy without explicit approval.

**Inputs may include:** product grid screenshots; shop/carousel screen grabs; product imagery on job; manual names/URLs; future CSV; future Shopify/Etsy/API; future structured product feed.

**Responsibilities:** Identify product names where visible/provided; captions/alt-text candidates; descriptions where provided; offers/links **only if explicitly supplied**; product-to-video associations; product-friendly schema fields with evidence; Hosted Manifest / product manifest enrichment; product discovery metadata for AI/search/chat surfaces.

**Structured outputs:** `ProductSignalReport`, `ProductItemCandidate`, `ProductVisualEvidence`, `ProductToContentAssociation`, `ProductManifestEnrichment`, `ProductGridQualityReport` (see `docs/phase7-product-grid-extension.md`).

**Hard rules:** no invented prices; no invented claims; no invented affiliate links; no fake stock/availability; no unsupported brand claims; no ecommerce checkout in Phase 7; no scraping external shops without future allow-listed connector.

**UI implications:** optional upload slot; dashboard/output sections only when data exists; no promise of full sync until backend supports it.

---

### 3.5 Verifier / Sense-Check Agent

**Owns:** grounding against **transcript**, **visual evidence**, **product evidence**.

**Responsibilities:** Classify claims supported | weakly supported | unsupported; flag hallucinated entities, overconfident language, weak CTAs, **unsupported product details**; produce `VerificationReport`.

**Hard rules:** does not invent sources; does not browse the web; only references evidence in the job bundle; unsupported claims cannot become final customer-visible facts.

---

### 3.6 Editor / Governor

**Owns:** FeedFoundry quality and customer-visible safety.

**Responsibilities:** Remove slop, repetition, spammy GEO, fake authority, keyword stuffing, misleading medical/legal/financial certainty; enforce terminology (**processing minutes/time**, annual archive — not credits/tokens as customer language); block **SEO spam dressed as GEO**; block fake citations and fake product claims.

**Hard rules:** no customer-visible output unless this passes.

---

### 3.7 Repository Beacon / GEO Freshness Agent

**Owns:** archive/repository freshness over time.

**Responsibilities:** Inspect Hosted Manifest and stored outputs; stale metadata; missing FAQs; thin factsheets; missing CTAs; weak AI-readable fields; **weak product discoverability**; emit `RepositoryFreshnessRecommendation` (prioritised, rationale, confidence).

**Hard rules:** recommend, do not blindly rewrite; no fake GEO; no synthetic backlinks; no mass auto-publication.

---

### 3.8 Cost / Routing Controller

**Owns:** provider/model routing, costs, rate limits, retries, fallback.

**Baseline:** OpenAI for v1 **config** — **not** a hard architectural lock; adapters for Gemini, Claude, Groq, DeepSeek, Mistral, local/open models.

**Responsibilities:** Stage-specific model selection; per-call and per-job and per-org caps; token **estimate** pre-flight, **actual** post-call; 429 handling; backoff/jitter; circuit breakers; fallback if schema-compatible and budget allows.

**Margin note:** design allows later evaluation of lighter/cheaper models for selected stages **without** rewriting product — via routing table + cost logs.

**Hard rules:** no infinite retries; no uncontrolled spend; no provider calls from browser; fail closed if cap exceeded.

---

### 3.9 Output Validator

**Owns:** machine validation of every AI artifact (Pydantic / JSON Schema).

**Responsibilities:** Reject malformed JSON, missing fields, invalid time ranges, unsupported fields; classify retryable vs fatal; store diagnostics in AI run logs.

**Hard rules:** no customer-visible output without validation; no silent schema drift; every document has `schema_version`.

---

### 3.10 Support / Product Intelligence Logger

**Owns:** operational intelligence from failures and patterns.

**Responsibilities:** Provider failures; validation failures; repeated transcript/visual/**product-grid** failures; UI/API confusion signals; cancellation mid-flight; redact sensitive data; audit-friendly stage records.

**Hard rules:** no unnecessary private data; no raw secrets; retention/compliance TBD in docs.

---

## 4. Provider interface (agnostic)

```text
AIProvider.complete(request) -> AIProviderResponse
```

**Request (logical):** `stage_name`, `schema_name`, `schema_version`, `prompt_version`, `model`, `input_bundle`, `max_tokens`, `temperature`, `timeout`, `cost_cap`, `trace_id`.

**Response (logical):** `parsed_json`, optional `raw_text`/`raw_payload` if safe to store, token usage, cost estimate/actual, latency, provider request id, finish reason, retry metadata.

**Config env (placeholders in runbook, not secrets):** `AI_PROVIDER`, `AI_MODEL`, `AI_FALLBACK_PROVIDER`, `AI_FALLBACK_MODEL`, `AI_ENABLE_MOCK_PROVIDER`, `AI_STRUCTURED_OUTPUTS_ENABLED`, `AI_VISUAL_ANALYSIS_ENABLED`, `AI_REPOSITORY_BEACON_ENABLED`, `AI_PRODUCT_GRID_ENABLED`, `AI_STORE_RUN_LOGS`, plus caps/timeouts/retries — see `docs/phase7-railway-storage-provider-architecture.md`.

**Rules:** structured outputs preferred where supported; **local schema validation always**; provider quirks behind adapter; **mock provider mandatory** for tests — no real network in default CI.

---

## 5. Job lifecycle mapping

States: `uploaded` → `queued` → `processing` → `completed` | `failed` | `cancelled`.

- AI starts only when **required artifacts** exist (e.g. transcript path resolved per pipeline).
- **Cancellation:** cooperative checks between chunks/stages; pending stages stopped.
- **Failed validation:** nothing customer-visible promoted; structured error in logs.
- **Partial outputs:** only if schema-valid **and** governor-approved; explicit incomplete metadata on job or artifact.
- **Scenarios** (Captain must define exact state transitions): transcript OK / AI enrichment fail; visual fail; product imagery unreadable; rate limit; malformed JSON; verifier/governor reject; cancel mid-AI; AI cap exceeded.

**Accounting (design decision — not implemented until approved):** Captain must document where **internal AI cost** differs from **customer processing minutes**. Questions: does successful AI enrichment affect `actual_processing_minutes_charged`? Is AI cost v1 internal margin only? Optional stages gated by plan? Cancellation vs in-flight AI cost? Customer-visible vs admin-only metrics — see checklist.

---

## 6. Structured output contracts (names)

Every schema includes: `schema_version`, `job_id` or artifact reference, `confidence` where appropriate, `evidence_references` where appropriate, `created_at`, `module`/`stage_name`, `validation_status`.

**Core:** Factsheet, FAQ, Chapters, Metadata, CTAs, Hosted Manifest enrichment, GEO/chat/search knowledge object.

**Visual:** VisualAnalysisReport, VisualEvidenceItem, OCRItem, KeyframeSummary, VisualMismatchFlag.

**Product:** ProductSignalReport, ProductItemCandidate, ProductVisualEvidence, ProductToContentAssociation, ProductManifestEnrichment, ProductGridQualityReport.

**Governance:** VerificationReport, OutputQualityReport, GovernorDecision, UnsupportedClaimFlag, CaveatNote.

**Ops:** AIRunLog, AIStageLog, CostRoutingDecisionLog, ProviderCallLog, RepositoryFreshnessRecommendation.

---

## 7. Risk register (living)

See `docs/phase7-implementation-checklist.md` — includes: cost runaway; chunking failure; malformed JSON; hallucinations; unsupported/product claims; weak visual/product extraction; rate limits; stuck jobs; cancel not interrupting; secrets; Railway/storage lock-in; OpenAI-only coupling; customer slop; fake GEO; over-autonomous agents early; **pricing drift into “credits”**; **UI promising product features before backend exists**.

---

## 8. Implementation gate

**No Phase 7B/C coding** until Steve explicitly approves **GO Phase 7A** (docs committed) then **GO Phase 7B** (parallel agents) then **GO Phase 7C** (implementation lanes). No OpenAI/provider calls from automation until approved.
