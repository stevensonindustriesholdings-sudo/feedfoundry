from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.models import MediaAsset, MediaAssetStatus, MediaType
from app.schemas.api import PresignUploadRequest, PresignUploadResponse
from app.services import annual_access as annual_access_svc
from app.services import storage as storage_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


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

    asset = MediaAsset(
        organisation_id=organisation_id,
        original_filename=body.filename,
        media_type=mt,
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
