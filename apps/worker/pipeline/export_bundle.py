from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def build_bundle_index(
    *,
    job_id: str,
    organisation_id: str,
    media_asset_id: str | None,
    outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "job_id": job_id,
        "organisation_id": organisation_id,
        "media_asset_id": media_asset_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "outputs": outputs,
    }


def bundle_json_bytes(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc, indent=2).encode("utf-8")
