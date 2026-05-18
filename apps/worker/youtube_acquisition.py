"""YouTube source acquisition (worker-side).

``FF_YOUTUBE_SOURCE_ACQUISITION_LIVE=1`` selects the real acquisition path when implemented.
Until then, intake uses ``youtube_stub`` media rows and the worker runs the deterministic stub pipeline.
"""

from __future__ import annotations

import os


def youtube_source_acquisition_live_enabled() -> bool:
    return os.environ.get("FF_YOUTUBE_SOURCE_ACQUISITION_LIVE", "").strip().lower() in ("1", "true", "yes")
