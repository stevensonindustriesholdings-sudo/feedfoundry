"""Output bundle and job output typing helpers."""

from __future__ import annotations

from enum import Enum


class ApiRequestedOutput(str, Enum):
    TRANSCRIPT = "transcript"
    CLEAN_TRANSCRIPT = "clean_transcript"
    CHAPTERS = "chapters"
    CLIP_CANDIDATES = "clip_candidates"
    SHOW_NOTES = "show_notes"
    METADATA = "metadata"
    CTAS = "ctas"
    FACT_SHEET = "fact_sheet"
    FAQS = "faqs"
    HOSTED_MANIFEST = "hosted_manifest"
    EXPORT_BUNDLE = "export_bundle"
