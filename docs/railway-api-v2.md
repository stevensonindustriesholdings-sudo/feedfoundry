# Create a fresh Railway API service (`api-v2`)

Use this when an existing API service is misconfigured (wrong source, npm commands, stale region). **Do not** delete Postgres, Redis, the GitHub repo, or the old API service until `api-v2` returns **`GET /health` → 200**.

`main` must include commit **`9dec025`** (`fix(api): staging bootstrap so /health can pass before full R2/Stripe env`). Verify on GitHub: **Commits → `main`**.

---

## 1. Create the service

1. Railway project → **New** → **Empty service** (or **GitHub** → add service).
2. Rename the service to **`api-v2`**.

---

## 2. Source (GitHub + Dockerfile)

| Field | Value |
|--------|--------|
| **Source** | GitHub → **`stevensonindustriesholdings-sudo/feedfoundry`** |
| **Branch** | **`main`** |
| **Root directory** | **`.`** or empty |
| **Builder** | **Dockerfile** |
| **Dockerfile path** | **`apps/api/Dockerfile`** |
| **Source image** | None / disconnected (not Hub `python:3.12-slim` only) |
| **Pre-deploy command** | *(blank)* |
| **Custom start command** | *(blank)* — use image **`CMD`** (`sh` + `uvicorn` + `${PORT:-8000}`) |

If **GitHub repo not found**, fix **GitHub → Settings → Applications → Railway → Configure** repository access, then reconnect.

---

## 3. Region

In service **Settings → Region**, pick a **current** region from the dropdown (e.g. US West / EU West per Railway’s list). **Do not** paste a stale custom value like **`iad`** if the UI marks it invalid.

---

## 4. Public networking

1. **Networking** (or **Settings → Networking**): **Public** / **Generate domain**.
2. **Target port:** **`8000`** unless runtime logs show Uvicorn on another port (then match Railway’s injected **`PORT`** from logs, e.g. `Uvicorn running on http://0.0.0.0:XXXX`).

---

## 5. Variables (names only; do not commit secrets)

Add on **`api-v2`** (copy from old service where helpful):

| Variable | Notes |
|----------|--------|
| **`APP_ENV`** | **`staging`** |
| **`DATABASE_URL`** | Reference or paste from existing **Postgres** service (same DB as before is fine). |
| **`FF_INTERNAL_API_KEY`** | Real secret (not `replace_me`). |
| **`PUBLIC_API_BASE_URL`** | Set to **`https://<api-v2-public-host>``** after** the domain exists (then **Redeploy** once if validation or redirects care about this URL). |

Optional (recommended when you have them; **`GET /health`** in staging should still work without them after **`9dec025`**):

- **`STRIPE_SECRET_KEY`**, **`STRIPE_WEBHOOK_SECRET`**, price IDs as in `.env.example`
- **`R2_*`** bucket and credential variables as in `.env.example`

**`PORT`:** Do **not** add a manual **`PORT`** variable unless you intentionally mirror the listen port (e.g. **`8000`**). Prefer letting Railway inject **`PORT`**.

---

## 6. Health check

| Field | Value |
|--------|--------|
| **Path** | **`/health`** |
| **Timeout** | **60** or **120** seconds for first deploy |

---

## 7. Deploy

1. Trigger deploy from **`main`** (latest should be **`9dec025`**).
2. **Build logs:** must show **`apps/api/Dockerfile`**, **`COPY ai-routing.yaml`**, **`COPY apps/api/app`**, **`pip install`** from **`requirements.txt`** — not npm, not image-only slim with no `COPY`.

---

## 8. Runtime logs (after “Starting Container”)

Confirm:

- **`Uvicorn running on http://0.0.0.0:`** …
- No **`ModuleNotFoundError`**
- No **`DATABASE_URL` missing`** / **`Invalid configuration`** for the minimal bootstrap (staging + DB + real `FF_INTERNAL_API_KEY`)
- No invalid **region** errors
- No **`npm`**

If the first **traceback** appears, fix **that** blocker only (or paste redacted logs).

---

## 9. Smoke test (replace host)

```bash
export API=https://<api-v2-domain>.up.railway.app   # or your generated URL

curl -i "$API/health"
curl -i "$API/ready"
curl -sS -o /dev/null -w "docs:%{http_code}\n" "$API/docs"
curl -sS -o /dev/null -w "openapi:%{http_code}\n" "$API/openapi.json"
```

**Success:** **`/health`** → **200** with JSON **`"status":"ok"`**.  
**`/ready`:** **200** or **503**; JSON **`checks`** keys include **`database`**, **`r2`**, **`stripe`**, **`internal_api`**, **`app`**, **`worker_settings`**, **`ai_providers`** — report **subsystem names** and **`ready`** booleans only (no secrets).

---

## 10. After success

- **Do not** delete the old API service until you confirm.
- **Do not** change worker until **`api-v2` `/health`** is stable.
- **Do not** keep editing startup code if **`/health`** is already **200**.

---

## Agent limitations (Cursor)

This agent **cannot** click Railway UI, create **`api-v2`**, or read your private deploy logs. Complete **§1–§9** in the browser; use this file as the checklist.
