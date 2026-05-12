from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.env_validation import validate_startup_bootstrap
from app.routes import (
    admin,
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


app = FastAPI(title="FeedFoundry API", lifespan=lifespan)

app.include_router(observability.router)
app.include_router(health.router, prefix="/v1")
app.include_router(uploads.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(outputs.router, prefix="/v1")
app.include_router(credits.router, prefix="/v1")
app.include_router(manifests.router, prefix="/v1")
app.include_router(stripe_webhooks.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
