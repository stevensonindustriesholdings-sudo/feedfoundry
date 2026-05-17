"""
Skunk Works shared video/commerce contract bridge (documentation-first).

Canonical contracts live in the CEO monorepo (TypeScript):
  ``<CEO>/packages/si-video-composition/`` — also aliased **si-video-engine** in CEO docs.

Vendored JSON snapshot (offline reference, safe to import in workers):
  ``<repo>/vendor/stevenson-contracts/product_template_ids.v1.json``

No import-time network I/O. Optional file read only when callers invoke ``load_vendored_product_template_ids``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TEMPLATE_IDS = REPO_ROOT / "vendor" / "stevenson-contracts" / "product_template_ids.v1.json"


def load_vendored_product_template_ids() -> dict[str, Any]:
    """Return parsed template-id snapshot, or empty dict if vendored file is absent."""
    if not VENDOR_TEMPLATE_IDS.is_file():
        return {}
    return json.loads(VENDOR_TEMPLATE_IDS.read_text(encoding="utf-8"))
