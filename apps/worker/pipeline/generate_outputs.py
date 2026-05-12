from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def stub_output(module: str, transcript: str) -> dict[str, Any]:
    """Placeholder until AI router + providers are wired end-to-end."""
    return {"module": module, "stub": True, "preview_chars": min(200, len(transcript))}
