from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False)
internal_key_header = APIKeyHeader(name="X-FF-Internal-Key", auto_error=False)
organisation_header = APIKeyHeader(name="X-FF-Organisation-Id", auto_error=False)
org_id_header_alt = APIKeyHeader(name="X-Org-Id", auto_error=False)


def verify_internal_key(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_ff_key: Optional[str] = Depends(internal_key_header),
) -> None:
    """
    Accept `Authorization: Bearer <FF_INTERNAL_API_KEY>` (preferred for Base44 proxies)
    or legacy `X-FF-Internal-Key`.
    """
    token: Optional[str] = None
    if bearer and bearer.scheme.lower() == "bearer":
        token = bearer.credentials
    elif x_ff_key:
        token = x_ff_key
    expected = get_settings().ff_internal_api_key
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials",
        )


def require_organisation_id(
    org_primary: Optional[str] = Depends(organisation_header),
    org_alt: Optional[str] = Depends(org_id_header_alt),
) -> str:
    org_id = org_primary or org_alt
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Org-Id or X-FF-Organisation-Id required",
        )
    return org_id
