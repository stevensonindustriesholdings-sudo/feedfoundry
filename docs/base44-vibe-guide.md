# Base44 product layer — vibe guide

FeedFoundry’s **engine** in this monorepo is intentionally unglamorous: JSON, presigned URLs, job states, and OpenAPI.

Base44 should feel like a **creator archive foundry**:

- **Forging metaphor**: uploads enter the furnace; structured artifacts emerge ready to publish.
- **Trust**: clear **processing allowance** (**processing minutes** / **processing hours**) and **annual hosted archive** status, plus job progress—no black box. Never frame the product as monthly SaaS; optional add-ons are **processing minute** top-ups. Avoid the word **“credits”** except when documenting **deprecated compatibility** fields or routes for integrators.
- **Outputs first**: surface transcript, chapters, show notes, metadata, CTAs, facts, FAQs, manifest, and export in scannable layouts.
- **No secrets in the browser**: all Stripe and AI keys stay on Railway or in Base44 **backend functions** that proxy to Railway with server-side credentials.

**Errors:** consumers should expect a **flat** JSON body: `{"code":"…","message":"…","fields":[]}` on error responses.

**Cancel:** a **Cancel job** action maps to `POST /v1/jobs/{job_id}/cancel`. When cancellation succeeds, reserved **processing minutes** are released; **cancelled** jobs do not consume completed allowance the way **completed** jobs do.

Visual tone: confident, craft-oriented, slightly industrial, creator-positive—not generic “AI SaaS” gradient blobs.
