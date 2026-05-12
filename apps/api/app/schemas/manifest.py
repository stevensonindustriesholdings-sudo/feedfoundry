"""Pydantic views for hosted manifest payloads (subset; full schema in packages/schemas)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class HostedManifestStub(BaseModel):
    """Minimal shape for validation in API; worker fills full schema."""

    schema_version: str = "1.0"
    creator_slug: str
    asset_slug: str
    canonical_title: str
    summary: str
    raw: Optional[Dict[str, Any]] = None
