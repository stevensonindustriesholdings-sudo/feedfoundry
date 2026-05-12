from __future__ import annotations

from typing import Any


def basic_qa(outputs: dict[str, Any], *, require_transcript: bool = True) -> tuple[bool, str | None]:
    if require_transcript and not outputs.get("raw_transcript"):
        return False, "missing_transcript"
    return True, None
