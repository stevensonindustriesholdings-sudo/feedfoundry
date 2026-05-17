# Night push — FeedFoundry

## URLs

- **API (live):** https://api-v2-iqho-production.up.railway.app — `GET /health` **200** (verified curl).
- **Web:** No dedicated `feedfoundry-web` service in `config/railway-products.json` (API + worker only). Deploy Next.js `apps/web` when a Railway web service exists, or run locally with `FEEDFOUNDRY_API_BASE_URL` + `FEEDFOUNDRY_INTERNAL_API_KEY`.

## Features shipped (this repo)

- **`/portal`** — Customer/admin view: YouTube enqueue + org queue + admin YouTube queue + provider config table + worker hints + recent jobs + output placeholders; clear **401** guidance (proxy key mismatch).
- **BFF allowlist** (`apps/web/src/app/api/ff/[...path]/route.ts`) — Adds `GET`/`POST` `/v1/youtube-source-queue`, admin `GET` `/v1/admin/youtube-queue`, `/v1/admin/jobs`, `/v1/admin/provider-configs`, and `GET` `/v1/system/worker-hints` (fixes prior `path_not_allowed` for jobs page hints and YouTube calls).
- **Nav** — Portal link in `AppNav`.
- **Types** — `AdminYoutubeQueueResponse`, `AdminProviderConfigsResponse`, etc.

## Real sources / providers

- **YouTube queue:** Records public URL shape only (existing API contract); no scraping.
- **Providers:** Read-only listing from `GET /v1/admin/provider-configs` (no keys in model).

## Branch

- `feat/feedfoundry-live-customer-admin-ui` (create from prior feature branch if needed).

## What Steve clicks

1. Open **`/portal`** after deploying web or locally (`npm run dev` in `apps/web`).
2. Paste a valid `youtube.com` / `youtu.be` URL → **Enqueue**; confirm row in **Your organisation** table.
3. **Admin — all organisations** table if internal key matches (same BFF key as API).
4. If red auth banner: fix server env `FEEDFOUNDRY_INTERNAL_API_KEY` = API `FF_INTERNAL_API_KEY`.

## Blockers

- **Web not on Railway** in current product manifest — only API/worker services listed.

## Next command

```bash
cd apps/web && npm run build
# When a Railway web service exists:
# cd repo root && ./scripts/railway_superpowers.sh deploy-one "$(pwd)" feat/feedfoundry-live-customer-admin-ui <web-service-name>
```

## Commit

Record SHA after commit: `git rev-parse HEAD` on branch `feat/feedfoundry-live-customer-admin-ui`.
