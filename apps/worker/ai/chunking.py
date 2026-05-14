"""Transcript text chunking utilities (skeleton — character windows with overlap)."""

from __future__ import annotations


def chunk_transcript_text(
    text: str,
    *,
    max_chars: int,
    overlap: int,
) -> list[tuple[int, int, str]]:
    """Split *text* into ``(start_char, end_char_exclusive, chunk)`` windows.

    - ``overlap`` repeats tail of previous chunk at the start of the next window.
    - Empty *text* yields an empty list.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be in [0, max_chars)")

    stripped = text
    if not stripped:
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0
    n = len(stripped)
    while start < n:
        end = min(n, start + max_chars)
        piece = stripped[start:end]
        chunks.append((start, end, piece))
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks
