# Railway config snippets (reference only)

Railway reads **per-service** settings from the dashboard (or linked config). These JSON files are **not** auto-applied unless you paste equivalent values into each service.

| File | Use for |
|------|---------|
| [`railway.json`](railway.json) | **API** service: Dockerfile `apps/api/Dockerfile`, health check `/health`. |
| [`railway.worker.json`](railway.worker.json) | **Worker** service: Dockerfile `apps/worker/Dockerfile`, no HTTP health check. |

Both require **repository root** as the Docker build context so `COPY ai-routing.yaml` and `COPY apps/...` succeed.

See **[docs/deployment-railway.md](../../docs/deployment-railway.md)** for the full GitHub + monorepo setup checklist.
