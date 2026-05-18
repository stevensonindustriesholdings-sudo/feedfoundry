from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.env_validation import validate_startup_bootstrap
from app.routes import (
    admin,
    catalog,
    credits,
    health,
    intake,
    jobs,
    manifests,
    observability,
    outputs,
    stripe_webhooks,
    system_surface,
    uploads,
    youtube_queue,
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
    {"name": "system", "description": "Internal worker / provider hints (no secrets)."},
    {"name": "youtube_source_queue", "description": "Enqueue-only YouTube URL backlog (no scraping)."},
    {
        "name": "intake",
        "description": "Launch MVP intake: gated YouTube video→job, playlist parent row, upload→job shortcut.",
    },
]

app = FastAPI(title="FeedFoundry API", lifespan=lifespan, openapi_tags=_OPENAPI_TAGS)


def _flatten_error_payload(detail: Any) -> dict[str, Any]:
    """Map any HTTPException ``detail`` shape to the canonical flat body.

    Canonical wire shape:
        {"code": "...", "message": "...", "fields": []}

    Supports three input forms produced by current routes:
      * dict carrying ``code`` (canonical ``problem()`` helper output)
      * legacy plain-string ``detail`` (older D-foundation routes)
      * any other object → coerced via ``str()``.
    """
    if isinstance(detail, dict) and "code" in detail:
        return {
            "code": str(detail.get("code")),
            "message": str(detail.get("message", detail.get("code", ""))),
            "fields": list(detail.get("fields", []) or []),
        }
    if isinstance(detail, str):
        return {"code": detail, "message": detail, "fields": []}
    return {"code": "http_error", "message": str(detail), "fields": []}


@app.exception_handler(StarletteHTTPException)
async def _flatten_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Uniform flat error envelope for both ``problem()`` and legacy string ``detail``."""
    return JSONResponse(status_code=exc.status_code, content=_flatten_error_payload(exc.detail))


@app.exception_handler(RequestValidationError)
async def _flatten_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "validation_error",
            "message": "Request validation failed.",
            "fields": jsonable_encoder(exc.errors()),
        },
    )


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
app.include_router(system_surface.router, prefix="/v1")
app.include_router(youtube_queue.router, prefix="/v1")
app.include_router(intake.router, prefix="/v1")
