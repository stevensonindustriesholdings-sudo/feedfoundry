"""Transcript-derived JSON outputs — deterministic, no external LLM.

Uses ``raw_transcript``-shaped payloads plus optional ``media_inspection`` payloads
produced earlier in the worker pipeline. Output Quality v0 polishes copy for
customer-facing artefacts while staying fully rule-based.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_STUB_NOISE = re.compile(
    r"\btranscript_stub_v0\s+job=\S+\s+media=\S+\s*\([^)]*\)\s*",
    re.IGNORECASE,
)


def derived_from_for_transcript(transcript: dict[str, Any]) -> str:
    """Label for downstream artefacts; ``transcript_stub`` unless OpenAI returned segments."""
    src = (transcript.get("source") or "").strip()
    if src == "openai_whisper":
        return "openai_whisper"
    return "transcript_stub"


def _clean_display_text(text: str) -> str:
    """Strip internal stub boilerplate so titles and summaries read like customer copy."""
    t = _STUB_NOISE.sub("", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _combined_text(transcript: dict[str, Any], *, max_chars: int = 12_000) -> str:
    parts: list[str] = []
    for seg in transcript.get("segments") or []:
        t = _clean_display_text((seg.get("text") or "").strip())
        if t:
            parts.append(t)
    out = " ".join(parts).strip()
    return out[:max_chars]


def _extract_summary(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _duration_human(seconds: Any) -> str | None:
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return None
    if s < 0.5:
        return None
    if s < 90:
        return f"About {s:.0f} seconds"
    m = int(s // 60)
    rem = int(round(s - 60 * m))
    if rem <= 0:
        return f"About {m} minutes"
    return f"About {m} min {rem} s"


def _chapter_title(index: int, text: str, total: int) -> str:
    cleaned = _clean_display_text(text)
    words = cleaned.split()[:10]
    lead = " ".join(words).strip()
    if not lead:
        return f"Chapter {index + 1}"
    if index == 0 and total > 1:
        prefix = "Opening — "
    elif index == total - 1 and total > 2:
        prefix = "Closing — "
    else:
        prefix = ""
    body = lead[0].upper() + lead[1:] if len(lead) > 1 else lead.upper()
    return (prefix + body)[:130]


def build_chapters_from_transcript(
    transcript: dict[str, Any],
    media_inspection: dict[str, Any] | None,
    *,
    derived_from: str,
) -> dict[str, Any]:
    del media_inspection  # reserved for future boundary hints
    segs = transcript.get("segments") or []
    chapters: list[dict[str, Any]] = []
    n = len(segs) or 1
    for i, seg in enumerate(segs):
        try:
            start = float(seg.get("start", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        text = (seg.get("text") or "").strip()
        cleaned = _clean_display_text(text)
        chapters.append(
            {
                "title": _chapter_title(i, text, max(n, 1)),
                "start_seconds": max(0.0, start),
                "summary": _extract_summary(cleaned, 420),
            }
        )
    if not chapters:
        combined = _combined_text(transcript, max_chars=2000)
        chapters.append(
            {
                "title": _chapter_title(0, combined, 1),
                "start_seconds": 0.0,
                "summary": _extract_summary(combined, 420),
            }
        )
    return {"schema_version": "1.0", "derived_from": derived_from, "chapters": chapters}


def _facts_from_text(text: str, *, max_facts: int = 8) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    t = (text or "").strip()
    if not t:
        return facts
    raw_parts = re.split(r"(?<=[.!?])\s+|\s*;\s+", t)
    candidates = [p.strip() for p in raw_parts if len(p.strip()) > 28]
    if len(candidates) < 2:
        candidates = [c.strip() for c in t.split("\n") if len(c.strip()) > 28]
    if not candidates:
        candidates = [t[:500]]
    seen: set[str] = set()
    span = 0.0
    for stmt in candidates:
        key = stmt.lower()[:72]
        if key in seen:
            continue
        seen.add(key)
        facts.append({"statement": stmt[:800], "source_span": f"t+{span:.1f}s"})
        span += 1.0
        if len(facts) >= max_facts:
            break
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
    preview = _extract_summary(combined, 520)
    mi = media_inspection or {}
    dur = None
    if mi.get("duration_seconds") is not None:
        try:
            dur = float(mi["duration_seconds"])
        except (TypeError, ValueError):
            dur = None
    dur_label = _duration_human(dur) if dur is not None else None
    vcodec = mi.get("video_codec")
    acodec = mi.get("audio_codec")
    container = mi.get("container_format")

    faqs: list[dict[str, Any]] = [
        {
            "question": "What is this episode about?",
            "answer": preview or "This pass synthesises structure and packaging from your transcript.",
        },
        {
            "question": "What video and audio formats were detected?",
            "answer": (
                f"Media inspection reports video codec {vcodec or 'unknown'} and "
                f"audio codec {acodec or 'none / unknown'}."
            ),
        },
    ]
    if dur_label:
        faqs.insert(
            1,
            {
                "question": "How long is the recording?",
                "answer": f"{dur_label} (from technical inspection).",
            },
        )
    if container:
        faqs.append(
            {
                "question": "What container format is the source file?",
                "answer": f"The file reads as: {container}.",
            }
        )
    lead_sentence = ""
    for part in re.split(r"(?<=[.!?])\s+", combined):
        if len(part.strip()) > 40:
            lead_sentence = part.strip()
            break
    if lead_sentence and len(faqs) < 8:
        faqs.append(
            {
                "question": "What is the main takeaway from the opening?",
                "answer": _extract_summary(lead_sentence, 400),
            }
        )
    faqs.append(
        {
            "question": "How was this content produced?",
            "answer": (
                "This bundle was generated with FeedFoundry's deterministic transcript pass "
                f"({derived_from}) — a fast, repeatable preview before optional paid AI enrichment."
            ),
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
    display = stem.replace("_", " ").replace("-", " ").strip() or "Episode"
    title = (display[:1].upper() + display[1:])[:120] if display else "Episode"
    combined = _combined_text(transcript, max_chars=6000)
    desc = _extract_summary(combined, 4000) or f"Transcript source={transcript.get('source')}"
    mi = media_inspection or {}
    dur_h = _duration_human(mi.get("duration_seconds"))
    tags = _topics_from_transcript(transcript, max_topics=12)
    return {
        "schema_version": "1.0",
        "derived_from": derived_from,
        "episode": {
            "display_title": title,
            "slug_hint": stem.lower().replace(" ", "-")[:80] or "episode",
            "duration_label": dur_h,
        },
        "youtube": {
            "title": title,
            "description": desc,
            "keywords": tags,
        },
        "podcast": {
            "title": title,
            "summary": _extract_summary(combined, 2000),
            "episode_notes": _extract_summary(combined, 900),
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
            "language_hint": "en",
        },
        "tags": tags,
    }


def _topics_from_transcript(transcript: dict[str, Any], *, max_topics: int = 8) -> list[str]:
    text = _combined_text(transcript, max_chars=8000).lower()
    words = [w for w in _WORD_RE.findall(text) if len(w) >= 5]
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
        "without",
        "there",
        "their",
        "which",
        "while",
        "where",
        "would",
        "could",
        "should",
    }
    words = [w for w in words if w not in stop]
    ctr = Counter(words)
    topics = [w for w, _ in ctr.most_common(max_topics * 2)]
    out: list[str] = []
    seen: set[str] = set()
    for w in topics:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_topics:
            break
    if not out:
        out = ["episode", "archive"]
    return out


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
    display = stem.replace("_", " ").replace("-", " ").strip() or "Episode"
    canonical = (display[:1].upper() + display[1:])[:160] if display else "Episode"
    combined = _combined_text(transcript, max_chars=2500)
    summary = _extract_summary(combined, 720) or "Summary derived from transcript."
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

    meta_title = f"{canonical} | {creator_slug or 'show'}"
    meta_desc = _extract_summary(summary, 155)

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
        "ctas": [
            {
                "label": "Open full transcript",
                "intent": "read_transcript",
                "url": None,
            }
        ],
        "links": {},
        "seo": {
            "meta_title": meta_title[:120],
            "meta_description": meta_desc,
            "keywords": topics[:16],
        },
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
