from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class TranscriptionBackend(Protocol):
    def transcribe_chunk(self, audio_path: str, *, language_hint: str | None = None) -> str: ...


def merge_transcripts(parts: list[str]) -> str:
    return "\n\n".join(p.strip() for p in parts if p.strip())
