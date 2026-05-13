"""Typed shapes for ``JobOutput.json_payload`` / storage payloads (Agent A/C contract hints).

These are documentation models; persistence remains JSON in ``job_outputs.json_payload``.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class RawTranscriptPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    segments: List[TranscriptSegment] = Field(default_factory=list)


class ChapterItem(BaseModel):
    title: str
    start_seconds: float


class ChaptersPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    chapters: List[ChapterItem] = Field(default_factory=list)


class FactItem(BaseModel):
    statement: str


class FactSheetPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    facts: List[FactItem] = Field(default_factory=list)


class FaqItem(BaseModel):
    question: str
    answer: str


class FaqsPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    faqs: List[FaqItem] = Field(default_factory=list)


class MetadataPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    youtube: dict[str, Any] = Field(default_factory=dict)
    podcast: dict[str, Any] = Field(default_factory=dict)


class CtasPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    ctas: List[dict[str, Any]] = Field(default_factory=list)


class HostedManifestPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    creator_slug: str = ""
    asset_slug: str = ""
    canonical_title: str = ""
    summary: str = ""
    chapters: List[dict[str, Any]] = Field(default_factory=list)
    topics: List[dict[str, Any]] = Field(default_factory=list)
    facts: List[dict[str, Any]] = Field(default_factory=list)
    faqs: List[dict[str, Any]] = Field(default_factory=list)
    ctas: List[dict[str, Any]] = Field(default_factory=list)
    links: dict[str, Any] = Field(default_factory=dict)


class ExportBundlePayload(BaseModel):
    """Pointer bundle for downloadable archive exports."""

    schema_version: Literal["1.0"] = "1.0"
    archive_format: Optional[str] = None
    storage_key: Optional[str] = None
    checksum_sha256: Optional[str] = None


class ShowNotesPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    markdown: str = ""


class ClipCandidatesPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    clips: List[dict[str, Any]] = Field(default_factory=list)
