"""Transcript-derived JSON outputs v0 — deterministic, no external LLM.

Uses ``raw_transcript``-shaped payloads plus optional ``media_inspection`` payloads
produced earlier in the worker pipeline.
"""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def derived_from_for_transcript(transcript: dict[str, Any]) -> str:
    """Label for downstream artefacts; ``transcript_stub`` unless OpenAI returned segments."""
    src = (transcript.get("source") or "").strip()
    if src == "openai_whisper":
        return "openai_whisper"
    return "transcript_stub"


def _combined_text(transcript: dict[str, Any], *, max_chars: int = 12_000) -> str:
    parts: list[str] = []
    for seg in transcript.get("segments") or []:
        t = (seg.get("text") or "").strip()
        if t:
            parts.append(t)
    out = " ".join(parts).strip()
    return out[:max_chars]


def _title_from_segment(text: str, index: int) -> str:
    words = (text or "").split()
    chunk = " ".join(words[:10]).strip()
    if not chunk:
        return f"Segment {index + 1}"
    return chunk[:120] + ("…" if len(chunk) > 119 else "")


def build_chapters_from_transcript(
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    *,
    derived_from: str,
) -> dict[str, Any]:
    del media_inspection  # reserved for future boundary hints
    segs = transcript.get("segments") or []
    chapters: list[dict[str, Any]] = []
    for i, seg in enumerate(segs):
        try:
            start = float(seg.get("start", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        text = (seg.get("text") or "").strip()
        chapters.append(
            {
                "title": _title_from_segment(text, i),
                "start_seconds": max(0.0, start),
                "summary": text[:400] + ("…" if len(text) > 400 else ""),
            }
        )
    if not chapters:
        combined = _combined_text(transcript, max_chars=2000)
        chapters.append(
            {
                "title": _title_from_segment(combined, 0),
                "start_seconds": 0.0,
                "summary": combined[:400],
            }
        )
    return {"schema_version": "1.0", "derived_from": derived_from, "chapters": chapters}


def _facts_from_text(text: str, *, max_facts: int = 8) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if not text.strip():
        return facts
    # Prefer sentence-like units; fall back to long clauses.
    raw_parts = re.split(r"(?<=[.!?])\s+", text)
    candidates = [p.strip() for p in raw_parts if len(p.strip()) > 24]
    if len(candidates) < 2:
        candidates = [c.strip() for c in text.split("\n") if len(c.strip()) > 24]
    if not candidates:
        candidates = [text.strip()[:400]]
    span = 0.0
    for stmt in candidates[:max_facts]:
        facts.append({"statement": stmt[:800], "source_span": f"t+{span:.1f}s"})
        span += 1.0
    return facts


def build_fact_sheet_from_transcript(
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    *,
    derived_from: str,
) -> dict[str, Any]:
    del media_inspection
    text = _combined_text(transcript)
    facts = _facts_from_text(text)
    if not facts:
        facts = [{"statement": text[:400] or "No transcript text available.", "source_span": None}]
    return {"schema_version": "1.0", "derived_from": derived_from, "facts": facts}


def build_faqs_from_transcript(
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    *,
    derived_from: str,
) -> dict[str, Any]:
    combined = _combined_text(transcript, max_chars=4000)
    dur = None
    if media_inspection:
        try:
            dur = float(media_inspection["duration_seconds"]) if media_inspection.get("duration_seconds") is not None else None
        except (TypeError, ValueError):
            dur = None
    container = (media_inspection or {}).get("container_format")
    preview = combined[:500] + ("…" if len(combined) > 500 else "")
    faqs: list[dict[str, Any]] = [
        {
            "question": "What is this episode about?",
            "answer": preview or "Content is derived from the transcript segments.",
        },
        {
            "question": "How was this FAQ generated?",
            "answer": f"Deterministic v0 from transcript (derived_from={derived_from}).",
        },
    ]
    if dur is not None:
        faqs.insert(
            1,
            {
                "question": "How long is the source media?",
                "answer": f"About {dur:.1f} seconds according to media inspection.",
            },
        )
    if container:
        faqs.append(
            {
                "question": "What container format was detected?",
                "answer": str(container),
            }
        )
    return {"schema_version": "1.0", "derived_from": derived_from, "faqs": faqs}


def build_metadata_from_transcript(
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    *,
    derived_from: str,
    original_basename: str | None,
) -> dict[str, Any]:
    stem = (original_basename or "episode").rsplit(".", 1)[0]
    title = stem.replace("_", " ").replace("-", " ")[:120] or "Episode"
    combined = _combined_text(transcript, max_chars=600)
    mi = media_inspection or {}
    return {
        "schema_version": "1.0",
        "derived_from": derived_from,
        "youtube": {
            "title": title,
            "description": combined[:4000] or f"Transcript source={transcript.get('source')}",
        },
        "podcast": {
            "title": title,
            "summary": combined[:2000] or "Summary derived from transcript text.",
        },
        "technical": {
            "container_format": mi.get("container_format"),
            "video_codec": mi.get("video_codec"),
            "audio_codec": mi.get("audio_codec"),
            "duration_seconds": mi.get("duration_seconds"),
            "file_size_bytes": mi.get("file_size_bytes"),
        },
        "transcript": {
            "source": transcript.get("source"),
            "segment_count": len(transcript.get("segments") or []),
        },
    }


def _topics_from_transcript(transcript: dict[str, Any], *, max_topics: int = 8) -> list[str]:
    text = _combined_text(transcript, max_chars=8000).lower()
    words = _WORD_RE.findall(text)
    seen: set[str] = set()
    topics: list[str] = []
    stop = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "have",
        "has",
        "was",
        "were",
        "are",
        "but",
        "not",
        "you",
        "your",
        "will",
        "can",
        "into",
        "about",
        "than",
        "then",
        "job",
        "media",
        "transcript",
        "stub",
        "external",
        "configured",
    }
    for w in words:
        if len(w) < 5 or w in stop or w in seen:
            continue
        seen.add(w)
        topics.append(w)
        if len(topics) >= max_topics:
            break
    if not topics:
        topics = ["transcript", "episode"]
    return topics


def build_hosted_manifest_from_transcript(
    *,
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    creator_slug: str,
    asset_slug: str,
    original_basename: str | None,
    outputs_available: list[str],
    derived_from: str,
) -> dict[str, Any]:
    stem = (original_basename or "episode").rsplit(".", 1)[0]
    canonical = stem.replace("_", " ").replace("-", " ")[:160] or "Episode"
    combined = _combined_text(transcript, max_chars=2500)
    summary = combined[:800] + ("…" if len(combined) > 800 else "") or "Summary derived from transcript."
    ch = build_chapters_from_transcript(transcript, media_inspection, derived_from=derived_from)["chapters"][:24]
    facts = build_fact_sheet_from_transcript(transcript, media_inspection, derived_from=derived_from)["facts"][:24]
    faqs = build_faqs_from_transcript(transcript, media_inspection, derived_from=derived_from)["faqs"][:12]
    topics = _topics_from_transcript(transcript)
    mi = media_inspection or {}
    duration = mi.get("duration_seconds")
    try:
        duration_seconds = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None

    return {
        "schema_version": "1.0",
        "creator_slug": creator_slug or "demo-creator",
        "asset_slug": asset_slug or "episode-001",
        "canonical_title": canonical,
        "summary": summary,
        "duration_seconds": duration_seconds,
        "chapters": [
            {"title": c["title"], "start_seconds": float(c["start_seconds"]), "summary": c.get("summary", "")}
            for c in ch
        ],
        "topics": topics,
        "facts": [{"statement": f["statement"], "source_span": f.get("source_span")} for f in facts],
        "faqs": faqs,
        "ctas": [],
        "links": {},
        "outputs_available": list(outputs_available),
        "derived_from": derived_from,
        "transcript_meta": {
            "source": transcript.get("source"),
            "segment_count": len(transcript.get("segments") or []),
            "combined_preview": combined[:280],
        },
        "media_meta": {
            "duration_seconds": mi.get("duration_seconds"),
            "video_codec": mi.get("video_codec"),
            "audio_codec": mi.get("audio_codec"),
            "container_format": mi.get("container_format"),
            "file_size_bytes": mi.get("file_size_bytes"),
        },
    }
