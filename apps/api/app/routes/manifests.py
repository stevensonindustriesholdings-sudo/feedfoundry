from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.db import get_session
from app.services.manifest_writer import find_manifest_payload

router = APIRouter(prefix="/manifests", tags=["manifests"])


@router.get("/{creator_slug}/{asset_slug}.json")
def get_hosted_manifest(
    creator_slug: str,
    asset_slug: str,
    session: Session = Depends(get_session),
):
    payload = find_manifest_payload(session, creator_slug=creator_slug, asset_slug=asset_slug)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="manifest_not_found")
    return JSONResponse(content=payload)
