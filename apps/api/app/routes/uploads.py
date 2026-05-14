from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.config.env_validation import is_strict_deployment_env
from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import MediaAsset, MediaAssetStatus, MediaType
from app.schemas.api import PresignUploadRequest, PresignUploadResponse
from app.services import annual_access as annual_access_svc
from app.services import storage as storage_service
from app.services.organisation_guard import ensure_org_row_for_internal_routes
from app.settings import get_settings

router = APIRouter(prefix="/uploads", tags=["uploads"])


class CompleteUploadRequest(BaseModel):
    """Optional client hints after PUT to the presigned URL (worker may still probe)."""

    media_asset_id: str
    duration_seconds: Optional[float] = Field(default=None, ge=0)


class CompleteUploadResponse(BaseModel):
    media_asset_id: str
    status: str


@router.post("/presign", response_model=PresignUploadResponse)
def presign_upload(
    body: PresignUploadRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> PresignUploadResponse:
    if not annual_access_svc.has_active_processing_entitlement(session, organisation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="annual_access_required",
        )
    try:
        mt = MediaType(body.media_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid media_type")

    ensure_org_row_for_internal_routes(session, organisation_id)

    settings = get_settings()
    if is_strict_deployment_env(settings.app_env) and not storage_service.storage_client_ready(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "storage_not_configured",
                "message": "Object storage credentials are not configured; uploads cannot be presigned.",
            },
        )

    asset = MediaAsset(
        organisation_id=organisation_id,
        original_filename=body.filename,
        media_type=mt,
        upload_content_type=body.content_type,
        storage_source_key="pending",
        file_size_bytes=body.file_size_bytes,
        status=MediaAssetStatus.UPLOADED,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)

    presigned = storage_service.presign_put_object(
        organisation_id=organisation_id,
        media_asset_id=asset.id,
        filename=body.filename,
        content_type=body.content_type,
    )
    asset.storage_source_key = presigned.storage_key
    session.add(asset)
    session.commit()

    return PresignUploadResponse(
        media_asset_id=asset.id,
        upload_url=presigned.upload_url,
        storage_key=presigned.storage_key,
        expires_in_seconds=presigned.expires_in_seconds,
    )


@router.post("/complete", response_model=CompleteUploadResponse)
def complete_upload_after_put(
    body: CompleteUploadRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> CompleteUploadResponse:
    """
    Call after the browser finishes PUT to the presigned URL so duration hints
    (optional) improve job estimates before the worker runs ffprobe.
    """
    if not annual_access_svc.has_active_processing_entitlement(session, organisation_id):
        raise problem(
            status_code=status.HTTP_403_FORBIDDEN,
            code="annual_access_required",
            message="Active annual hosted archive access is required.",
        )
    ma = session.get(MediaAsset, body.media_asset_id)
    if not ma or ma.organisation_id != organisation_id:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="media_asset_not_found",
            message="Media asset not found for this organisation.",
        )
    if body.duration_seconds is not None:
        ma.duration_seconds = body.duration_seconds
        session.add(ma)
    session.commit()
    session.refresh(ma)
    return CompleteUploadResponse(media_asset_id=ma.id, status=ma.status.value)
