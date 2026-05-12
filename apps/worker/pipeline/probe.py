from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Optional

log = logging.getLogger(__name__)


def ffprobe_json(path: str, *, ffprobe_binary: str = "ffprobe") -> Optional[dict[str, Any]]:
    try:
        proc = subprocess.run(
            [
                ffprobe_binary,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        log.warning("ffprobe_failed path=%s err=%s", path, e)
        return None
