"""Canonical structured HTTP errors.

Wire shape (flat at top level of the response body):

    {"code": "machine_readable_code", "message": "Human-readable message.", "fields": []}

Route handlers may ``raise problem(...)``. A FastAPI exception handler in
``app.main`` flattens both this helper's output and any legacy
``HTTPException(detail=...)`` raises to the canonical shape above so the
API contract is uniform regardless of how a handler reported the error.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import HTTPException, status


def problem(
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    code: str,
    message: str,
    fields: Optional[List[Any]] = None,
) -> HTTPException:
    """Build an HTTPException carrying the canonical flat error payload."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "fields": list(fields or [])},
    )
