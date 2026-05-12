from fastapi import APIRouter

from app.schemas.api import HealthResponse
from app.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=get_settings().api_version)
