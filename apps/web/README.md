# FeedFoundry Web (`apps/web`)

Customer-facing **Next.js (App Router)** app: **annual hosted archive** and **creator archive** positioning, **processing allowance** / **processing time** (avoid “credits” in customer copy), upload → job → outputs → public manifest — with **staging/debug** affordances embedded (System page, collapsible debug panels, smoke checks) without a separate “integration console.” Full stack setup: [docs/runbook.md](../../docs/runbook.md).

**Phase 7:** the web app never holds **AI provider** secrets. Server-only proxy keys only. Product **Product Grid** UX must stay **preview / optional** until the API exposes matching fields — see [docs/phase7-product-grid-extension.md](../../docs/phase7-product-grid-extension.md) and the [AI operating brief](../../docs/ai-operating-brief.md).

## Requirements

- Node **20+** recommended (Next 15).
- Running **FeedFoundry API** (staging URL below) with valid **`FF_INTERNAL_API_KEY`** for your org.

## Environment variables

Copy **`.env.example`** → **`.env.local`** (never commit secrets).

| Variable | Where | Purpose |
|----------|--------|---------|
| **`FEEDFOUNDRY_API_BASE_URL`** | Server only | Upstream API origin (no trailing slash). |
| **`FEEDFOUNDRY_INTERNAL_API_KEY`** | Server only | Bearer token for `/v1/*` via proxy. **Never** `NEXT_PUBLIC_*`. |
| **`FEEDFOUNDRY_DEFAULT_ORG_ID`** | Server only | Default `X-Org-Id` when the browser does not send `x-feedfoundry-org-id`. |
| **`NEXT_PUBLIC_APP_ENV`** | Public | e.g. `staging` — shows staging copy, org switcher, smoke helpers. |
| **`NEXT_PUBLIC_FEEDFOUNDRY_API_BASE_URL`** | Public | Used for **public** manifest fetches from the browser (no secret). |

**Security:** Only **Route Handlers** under `src/app/api/ff/[...path]` and **server modules** in `src/lib/server/` read the internal key. The browser calls **`/api/ff/...`**, not the raw API with secrets.

## Local development

From **repository root**:

```bash
cd apps/web
npm install
cp .env.example .env.local
# Edit .env.local — set FEEDFOUNDRY_INTERNAL_API_KEY to match Railway API service **api-v2-IQho** (FF_INTERNAL_API_KEY)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Next dev server on port 3000. |
| `npm run build` | Production build. |
| `npm run start` | Serve production build. |
| `npm run lint` | ESLint (Next core-web-vitals). |
| `npm run typecheck` | `tsc --noEmit`. |

## Architecture notes

- **Proxy:** `GET|POST /api/ff/*` with an allowlisted upstream path. Adds `Authorization: Bearer` + `X-Org-Id` server-side.
- **Org override (staging):** `OrgSwitcher` on **System** writes `ff_org_id` in `localStorage`; client fetches send header **`x-feedfoundry-org-id`** when set.
- **Job persistence:** `ff_latest_job_id` after successful job create from **Upload**; **Jobs** / **Outputs** pre-fill when present.
- **Manifest:** **Archive** page calls **`GET {NEXT_PUBLIC}/v1/manifests/{creator}/{asset}.json`** directly (public route, no internal key).

## Smoke path

On **Dashboard**, use **Backend smoke checks** (manual buttons). Full job-creation flow stays on **Upload** with explicit **“Confirm job creation”**; the API may **reserve estimated processing minutes** while a job is active, and releases that reservation on **failure** or **cancellation** (those terminal states do not debit actual processing time from the allowance).

## Staging API (current)

`https://api-v2-iqho-production.up.railway.app`

Do not commit production keys. Rotate any key pasted into chat or tickets.
