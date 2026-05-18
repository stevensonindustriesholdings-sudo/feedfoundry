"""Launch MVP intake — YouTube (gated), playlist parent rows, upload→job shortcut."""

from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import MediaAsset, MediaAssetStatus, MediaType, YoutubeSourceQueue
from app.routes.jobs import create_job
from app.routes.youtube_queue import YoutubeQueueEnqueueRequest
from app.schemas.api import CreateJobRequest, CreateJobResponse
from app.services.organisation_guard import OrganisationNotFound, ensure_org_row_for_internal_routes

router = APIRouter(prefix="/intake", tags=["intake"])

_PLAYLIST_URL = re.compile(
    r"^https?://(www\.)?youtube\.com/.*[?&]list=([a-zA-Z0-9_-]{10,})",
    re.IGNORECASE,
)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def youtube_source_acquisition_enabled() -> bool:
    """Default **off** — set ``FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED`` to opt in."""
    return _env_truthy("FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED")


def youtube_source_acquisition_live_enabled() -> bool:
    """When true, worker should attempt live public-URL acquisition instead of stub handling."""
    return _env_truthy("FF_YOUTUBE_SOURCE_ACQUISITION_LIVE")


def _is_missing_youtube_queue_schema(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "youtube_source_queue" in text and (
        "does not exist" in text or "no such table" in text or "undefinedtable" in text
    )


def _youtube_queue_schema_unavailable(exc: BaseException):
    if _is_missing_youtube_queue_schema(exc):
        raise problem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="youtube_intake_schema_unavailable",
            message=(
                "YouTube intake schema is unavailable: youtube_source_queue table is missing. "
                "Run the latest forward Alembic migration before retrying."
            ),
        ) from exc
    raise exc


def _raise_organisation_not_found() -> None:
    raise problem(
        status_code=status.HTTP_404_NOT_FOUND,
        code="organisation_not_found",
        message="Organisation does not exist for this request.",
        fields=["X-Org-Id"],
    )


def _ensure_known_organisation(session: Session, organisation_id: str) -> None:
    try:
        ensure_org_row_for_internal_routes(session, organisation_id)
    except OrganisationNotFound:
        _raise_organisation_not_found()


class IntakeYoutubeVideoRequest(BaseModel):
    youtube_url: str = Field(..., min_length=12, max_length=2048)
    requested_outputs: list[str] = Field(default_factory=lambda: ["transcript", "hosted_manifest"])
    distribution_targets: Optional[list[str]] = None


class IntakeYoutubeVideoResponse(BaseModel):
    status: str
    queue_id: str
    youtube_url: str
    media_asset_id: str
    job_id: str
    acquisition_status: str
    live_acquisition_enabled: bool
    estimated_processing_minutes: int
    reserved_processing_minutes: int
    estimated_processing_hours: float


class IntakeYoutubePlaylistRequest(BaseModel):
    playlist_url: str = Field(..., min_length=24, max_length=2048)


class IntakeYoutubePlaylistResponse(BaseModel):
    queue_id: str
    playlist_url: str
    status: str
    queue_kind: str
    detail: str = "Playlist recorded as parent — expansion not wired yet."


class IntakeUploadRequest(CreateJobRequest):
    """Same as ``POST /v1/jobs`` plus optional duration hint after browser PUT."""

    duration_seconds: Optional[float] = Field(default=None, ge=0)


@router.post("/youtube-video", response_model=IntakeYoutubeVideoResponse)
def intake_youtube_video(
    body: IntakeYoutubeVideoRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> IntakeYoutubeVideoResponse:
    if not youtube_source_acquisition_enabled():
        raise problem(
            status_code=status.HTTP_403_FORBIDDEN,
            code="youtube_intake_disabled",
            message="YouTube intake is disabled. Set FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED to enable.",
        )
    try:
        normalized = YoutubeQueueEnqueueRequest.validate_public_shape(body.youtube_url)
    except ValueError as e:
        raise problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="invalid_youtube_url",
            message=str(e),
        ) from e

    _ensure_known_organisation(session, organisation_id)

    row = YoutubeSourceQueue(
        organisation_id=organisation_id,
        youtube_url=normalized,
        status="queued",
        queue_kind="video",
        acquisition_status="intake_accepted",
        source_title=None,
        source_duration_seconds=None,
        temp_media_storage_key=None,
    )
    session.add(row)
    try:
        session.flush()
    except (OperationalError, ProgrammingError) as exc:
        session.rollback()
        _youtube_queue_schema_unavailable(exc)

    pending_key = f"ff-youtube-pending:{row.id}"
    media = MediaAsset(
        organisation_id=organisation_id,
        original_filename="youtube_source.mp4",
        media_type=MediaType.VIDEO,
        upload_content_type="video/youtube-intake",
        storage_source_key=pending_key,
        intake_kind="youtube_stub",
        status=MediaAssetStatus.UPLOADED,
    )
    session.add(media)
    session.flush()

    row.media_asset_id = media.id
    session.add(row)
    session.commit()
    session.refresh(media)
    session.refresh(row)

    job_body = CreateJobRequest(
        media_asset_id=media.id,
        requested_outputs=list(body.requested_outputs),
        distribution_targets=list(body.distribution_targets or []),
    )
    created = create_job(job_body, None, organisation_id, session)  # type: ignore[arg-type]

    row2 = session.get(YoutubeSourceQueue, row.id)
    if row2:
        row2.job_id = created.job_id
        row2.acquisition_status = "queued_for_worker"
        session.add(row2)
        session.commit()

    return IntakeYoutubeVideoResponse(
        status="queued",
        queue_id=row.id,
        youtube_url=normalized,
        media_asset_id=media.id,
        job_id=created.job_id,
        acquisition_status="queued_for_worker",
        live_acquisition_enabled=youtube_source_acquisition_live_enabled(),
        estimated_processing_minutes=created.estimated_processing_minutes,
        reserved_processing_minutes=created.reserved_processing_minutes,
        estimated_processing_hours=created.estimated_processing_hours,
    )


@router.post("/youtube-playlist", response_model=IntakeYoutubePlaylistResponse)
def intake_youtube_playlist(
    body: IntakeYoutubePlaylistRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> IntakeYoutubePlaylistResponse:
    if not youtube_source_acquisition_enabled():
        raise problem(
            status_code=status.HTTP_403_FORBIDDEN,
            code="youtube_intake_disabled",
            message="YouTube intake is disabled. Set FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED to enable.",
        )
    u = body.playlist_url.strip()
    if not _PLAYLIST_URL.match(u):
        raise problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="invalid_youtube_playlist_url",
            message="URL must be a public youtube.com link with a list= playlist id.",
        )

    _ensure_known_organisation(session, organisation_id)

    row = YoutubeSourceQueue(
        organisation_id=organisation_id,
        youtube_url=u,
        status="not_yet_expanded",
        queue_kind="playlist_parent",
        acquisition_status="not_yet_expanded",
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    return IntakeYoutubePlaylistResponse(
        queue_id=row.id,
        playlist_url=u,
        status=row.status,
        queue_kind=row.queue_kind,
    )


@router.post("/upload", response_model=CreateJobResponse)
def intake_upload_then_job(
    body: IntakeUploadRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> CreateJobResponse:
    """Register job for an uploaded asset (after presign PUT). Optional ``duration_seconds`` hint."""
    _ensure_known_organisation(session, organisation_id)
    ma = session.get(MediaAsset, body.media_asset_id)
    if ma and body.duration_seconds is not None:
        ma.duration_seconds = body.duration_seconds
        session.add(ma)
        session.commit()
        session.refresh(ma)

    job_body = CreateJobRequest(
        media_asset_id=body.media_asset_id,
        requested_outputs=list(body.requested_outputs),
        distribution_targets=list(body.distribution_targets or []),
    )
    return create_job(job_body, None, organisation_id, session)  # type: ignore[arg-type]
