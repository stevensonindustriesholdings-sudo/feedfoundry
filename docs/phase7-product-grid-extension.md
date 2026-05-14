# Phase 7 — Product Grid / Product Imagery extension

## Positioning

- **Launch wedge** remains: **video / audio / podcast** upload → transcript → archive / Hosted Manifest.
- **Product Grid / product imagery** is an **extension** of the media-to-AI-readable-repository workflow — **not** a pivot to ecommerce.
- **No** full Shopify/Etsy/sync, **no** checkout, **no** scraping external shops in Phase 7 unless Steve explicitly approves a bounded connector.

---

## Why it exists

Many creator/business episodes promote: products, courses, books, merch, affiliate items, Etsy/Shopify/own-shop goods, service packages, downloadable resources. FeedFoundry should optionally **structure** that signal when **evidence** exists (screens, spoken mentions, manual URLs) — without inventing commerce facts.

---

## Inputs (phased)

| Input | Phase 7 v1 | Later |
|-------|--------------|--------|
| Screenshots of product grids / shop UI | Optional upload / preview | |
| Product imagery attached to job | Optional | |
| Manual product names / URLs | Optional fields | |
| CSV import | **Coming soon** (UI greyed or labelled) | When approved |
| Shopify/Etsy/API | **Not in v1** | Allow-listed connector |

---

## Backend (planning — not implemented until GO Phase 7C)

- New **output kinds** (conceptual): product signal report, product manifest (or enrichment blob), associations table or JSON linkage on `job_outputs`.
- **Storage paths** for product images separate from source video; same S3-compatible adapter rules as other artifacts.
- **Schemas:** `ProductSignalReport`, `ProductItemCandidate`, `ProductVisualEvidence`, `ProductToContentAssociation`, `ProductManifestEnrichment`, `ProductGridQualityReport` — all with `schema_version`, evidence references, confidence, no invented prices/links.

---

## AI pipeline hooks

- **Visual Analyst** ingests product imagery / grid screenshots like other visual evidence.
- **Producer** treats spoken product claims as **claims** requiring evidence spans.
- **Verifier** rejects unsupported product details (price, availability, brand guarantees).
- **Governor** removes fake offers, urgency scams, invented discounts.
- **Repository Beacon** may recommend “thin product metadata” or missing product FAQs — **recommendations only**.

---

## UI / copy rules

- Upload flow: optional **“Product imagery / product grid context”** — clearly optional.
- Dashboard / outputs: show **Product signals** section **only when** validated data exists.
- Do **not** label features “Shopify connected” until backend supports it.
- Hosted Manifest: document **product-aware** optional fields in manifest contract (F + A coordination).

---

## Non-goals (repeated)

- Full ecommerce platform  
- Live inventory, checkout, tax/shipping  
- Unverified affiliate link injection  
- Web scraping of third-party shops without connector approval  

---

## Dependencies

- Feature flags: `AI_PRODUCT_GRID_ENABLED` (worker + UI gating).
- Captain plan includes Product Signal Extractor **only** when flag + inputs present.
