from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.env_validation import validate_startup_bootstrap
from app.routes import (
    admin,
    catalog,
    credits,
    health,
    jobs,
    manifests,
    observability,
    outputs,
    stripe_webhooks,
    uploads,
)
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    validate_startup_bootstrap(settings)
    yield


_OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness/readiness for orchestration and the `/system` dashboard proxy.",
    },
    {
        "name": "uploads",
        "description": "Presigned uploads of creator-owned media into object storage (no URL ingestion).",
    },
    {
        "name": "jobs",
        "description": "Create jobs, list recent jobs for an organisation, and poll processing status.",
    },
    {
        "name": "outputs",
        "description": "List generated artifacts for a job with time-limited download URLs.",
    },
    {
        "name": "account",
        "description": "Annual hosted archive status and remaining processing minutes (wallet view).",
    },
    {
        "name": "catalog",
        "description": "Static contract: which output kinds clients may request and which types workers persist.",
    },
    {"name": "manifests", "description": "Public hosted manifest JSON for archive pages."},
    {"name": "stripe_webhooks", "description": "Stripe webhook receiver (server-to-server only)."},
    {"name": "admin", "description": "Internal operator routes (requires internal API key)."},
    {"name": "observability", "description": "Version/build metadata and structured readiness checks."},
]

app = FastAPI(title="FeedFoundry API", lifespan=lifespan, openapi_tags=_OPENAPI_TAGS)

app.include_router(observability.router)
app.include_router(health.router, prefix="/v1")
app.include_router(uploads.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v1")
app.include_router(outputs.router, prefix="/v1")
app.include_router(credits.router, prefix="/v1")
app.include_router(manifests.router, prefix="/v1")
app.include_router(stripe_webhooks.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
