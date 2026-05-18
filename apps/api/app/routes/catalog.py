"""Public catalog of supported output kinds (API contract vs persisted rows)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import JobOutputType
from app.schemas.api import CatalogOutputKind, OutputCatalogResponse
from app.schemas.outputs import ApiRequestedOutput

router = APIRouter(prefix="/catalog", tags=["catalog"])

_REQUESTED: list[tuple[ApiRequestedOutput, str, str]] = [
    (ApiRequestedOutput.TRANSCRIPT, "Transcript", "Full transcript of the source media."),
    (ApiRequestedOutput.CLEAN_TRANSCRIPT, "Clean transcript", "Edited transcript suitable for publishing."),
    (ApiRequestedOutput.CHAPTERS, "Chapters", "Timestamped chapter boundaries."),
    (ApiRequestedOutput.CLIP_CANDIDATES, "Clip candidates", "Suggested short-form clip moments."),
    (ApiRequestedOutput.SHOW_NOTES, "Show notes", "Episode show notes / summary copy."),
    (ApiRequestedOutput.METADATA, "Metadata", "Structured metadata for the episode."),
    (ApiRequestedOutput.CTAS, "CTAs", "Calls to action derived from the episode."),
    (ApiRequestedOutput.FACT_SHEET, "Fact sheet", "Fact-checked or extracted factual bullets."),
    (ApiRequestedOutput.FAQS, "FAQs", "Frequently asked questions for the episode."),
    (ApiRequestedOutput.HOSTED_MANIFEST, "Hosted manifest", "Public JSON manifest for archive pages."),
    (ApiRequestedOutput.EXPORT_BUNDLE, "Export bundle", "Bundled export archive for download."),
]

_PERSISTED: list[tuple[JobOutputType, str, str]] = [
    (JobOutputType.RAW_TRANSCRIPT, "Transcript (raw)", "Stored transcript artifact (from transcript request)."),
    (JobOutputType.CLEAN_TRANSCRIPT, "Clean transcript", "Edited transcript output."),
    (JobOutputType.CHAPTERS, "Chapters", "Chapter JSON."),
    (JobOutputType.CLIP_CANDIDATES, "Clip candidates", "Suggested clips."),
    (JobOutputType.SHOW_NOTES, "Show notes", "Show notes markdown/HTML/JSON."),
    (JobOutputType.METADATA, "Metadata", "Metadata JSON."),
    (JobOutputType.CTAS, "CTAs", "CTA JSON or copy."),
    (JobOutputType.FACT_SHEET, "Fact sheet", "Fact sheet markdown/JSON."),
    (JobOutputType.FAQS, "FAQs", "FAQ markdown/JSON."),
    (JobOutputType.HOSTED_MANIFEST, "Hosted manifest", "Hosted manifest JSON."),
    (JobOutputType.EXPORT_BUNDLE, "Export bundle", "Zip or bundle object in object storage."),
    (JobOutputType.MEDIA_INSPECTION, "Media inspection", "ffprobe / validation diagnostics for the source file."),
    (JobOutputType.AGENT_BUNDLE, "Agent bundle", "Hermes-style deterministic agent bundle JSON (opt-in worker stage)."),
]


@router.get(
    "/outputs",
    response_model=OutputCatalogResponse,
    summary="Supported requested output slugs and persisted output types",
)
def get_output_catalog() -> OutputCatalogResponse:
    return OutputCatalogResponse(
        requested_output_kinds=[
            CatalogOutputKind(slug=e.value, title=t, description=d) for e, t, d in _REQUESTED
        ],
        persisted_output_types=[
            CatalogOutputKind(slug=e.value, title=t, description=d) for e, t, d in _PERSISTED
        ],
    )
