"""YouTube URL queue — records intent only; no download, scrape, or auth bypass."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import YoutubeSourceQueue

router = APIRouter(prefix="/youtube-source-queue", tags=["youtube_source_queue"])

_YOUTUBE_HOST = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?v=[\w-]{11}(&[^\s]*)?|shorts/[\w-]+|embed/[\w-]+)|youtu\.be/[\w-]{11}(\?[^\s]*)?)(\#[^\s]*)?$",
    re.IGNORECASE,
)


class YoutubeQueueEnqueueRequest(BaseModel):
    youtube_url: str = Field(..., min_length=12, max_length=2048, description="Public YouTube watch or short URL.")

    @staticmethod
    def validate_public_shape(url: str) -> str:
        u = url.strip()
        if not _YOUTUBE_HOST.match(u):
            raise ValueError("URL must be a public youtube.com or youtu.be link.")
        return u


class YoutubeQueueItemResponse(BaseModel):
    id: str
    youtube_url: str
    status: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    queue_kind: Optional[str] = None
    job_id: Optional[str] = None
    media_asset_id: Optional[str] = None
    acquisition_status: Optional[str] = None
    acquisition_error: Optional[str] = None
    source_title: Optional[str] = None
    source_duration_seconds: Optional[float] = None


class YoutubeQueueEnqueueResponse(BaseModel):
    id: str
    youtube_url: str
    status: str
    detail: str = "Queued for future processing — no media download or scraping has started."


class YoutubeQueueListResponse(BaseModel):
    items: list[YoutubeQueueItemResponse]
    total: int


@router.post("", response_model=YoutubeQueueEnqueueResponse)
def enqueue_youtube_url(
    body: YoutubeQueueEnqueueRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> YoutubeQueueEnqueueResponse:
    try:
        normalized = YoutubeQueueEnqueueRequest.validate_public_shape(body.youtube_url)
    except ValueError as e:
        raise problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="invalid_youtube_url",
            message=str(e),
        ) from e

    row = YoutubeSourceQueue(organisation_id=organisation_id, youtube_url=normalized, status="queued")
    session.add(row)
    session.commit()
    session.refresh(row)
    return YoutubeQueueEnqueueResponse(
        id=row.id,
        youtube_url=row.youtube_url,
        status=row.status,
    )


@router.get("", response_model=YoutubeQueueListResponse)
def list_queued_urls(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> YoutubeQueueListResponse:
    filters = [YoutubeSourceQueue.organisation_id == organisation_id]
    total = session.exec(select(func.count()).select_from(YoutubeSourceQueue).where(*filters)).one()
    stmt = (
        select(YoutubeSourceQueue)
        .where(*filters)
        .order_by(desc(YoutubeSourceQueue.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    items = [
        YoutubeQueueItemResponse(
            id=r.id,
            youtube_url=r.youtube_url,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at.isoformat() if r.created_at else None,
            queue_kind=getattr(r, "queue_kind", None) or "video",
            job_id=getattr(r, "job_id", None),
            media_asset_id=getattr(r, "media_asset_id", None),
            acquisition_status=getattr(r, "acquisition_status", None),
            acquisition_error=getattr(r, "acquisition_error", None),
            source_title=getattr(r, "source_title", None),
            source_duration_seconds=getattr(r, "source_duration_seconds", None),
        )
        for r in rows
    ]
    return YoutubeQueueListResponse(items=items, total=int(total))
