from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("feedfoundry.audit")


def log_admin_event(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    logger.info("%s %s", event, payload or {})
