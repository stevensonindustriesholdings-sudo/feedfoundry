from __future__ import annotations

from enum import Enum
from typing import Any, Final, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field

FACTSHEET_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.factsheet"
FACTSHEET_SCHEMA_VERSION: Final[str] = "1.0.0"


class FactsheetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    key_facts: list[str] = Field(default_factory=list)


FAQ_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.faq"
FAQ_SCHEMA_VERSION: Final[str] = "1.0.0"


class FAQItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str


class FAQPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FAQItem]


CHAPTERS_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.chapters"
CHAPTERS_SCHEMA_VERSION: Final[str] = "1.0.0"


class ChapterItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    start_ms: int = Field(ge=0)


class ChaptersPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapters: list[ChapterItem]


METADATA_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.metadata"
METADATA_SCHEMA_VERSION: Final[str] = "1.0.0"


class MetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_title: str
    speakers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


CTA_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.cta"
CTA_SCHEMA_VERSION: Final[str] = "1.0.0"


class CTAItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    placement: str


class CTAPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ctas: list[CTAItem]


HOSTED_MANIFEST_ENRICHMENT_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.hosted_manifest_enrichment"
HOSTED_MANIFEST_ENRICHMENT_SCHEMA_VERSION: Final[str] = "1.0.0"


class HostedManifestEnrichmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: str
    supplements: dict[str, Any] = Field(default_factory=dict)


VISUAL_ANALYSIS_REPORT_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.visual_analysis_report"
VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"


class VisualScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class KeyframeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str
    t_ms: int = Field(ge=0)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class OCRItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr_source_id: str
    t_ms: int = Field(ge=0)
    text_snippet: str
    confidence: float = Field(ge=0.0, le=1.0)


class VisualEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str
    t_ms: int = Field(ge=0)
    description: str
    ocr_source_id: Optional[str] = None
    product_image_id: Optional[str] = None


class VisualMismatchFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    detail: str
    severity: Literal["low", "medium", "high"] = "low"


class VisualAnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenes: list[VisualScene]
    dominant_colors: list[str] = Field(default_factory=list)
    keyframe_summaries: list[KeyframeSummary] = Field(default_factory=list)
    ocr_items: list[OCRItem] = Field(default_factory=list)
    visual_evidence: list[VisualEvidenceItem] = Field(default_factory=list)
    mismatch_flags: list[VisualMismatchFlag] = Field(default_factory=list)


VisualAnalysisReportPayload = VisualAnalysisReport


PRODUCT_SIGNAL_REPORT_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.product_signal_report"
PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"


class ProductSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class ProductCommerceClaimStatus(str, Enum):
    """Explicit non-assertive states — no definitive commerce claims in V1 skeleton."""

    UNKNOWN = "unknown"
    DEFERRED = "deferred"
    LOW_CONFIDENCE = "low_confidence"


class ProductItemCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    name_stub: str
    title_claim_status: ProductCommerceClaimStatus = ProductCommerceClaimStatus.UNKNOWN
    price_status: ProductCommerceClaimStatus = ProductCommerceClaimStatus.UNKNOWN
    availability_status: ProductCommerceClaimStatus = ProductCommerceClaimStatus.UNKNOWN
    external_link_status: ProductCommerceClaimStatus = ProductCommerceClaimStatus.DEFERRED


class ProductVisualEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_image_id: str
    frame_id: Optional[str] = None
    t_ms: Optional[int] = Field(default=None, ge=0)
    notes: str = ""


class ProductToContentAssociation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    association_id: str
    candidate_id: str
    content_anchor_ms: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)


class ProductGridQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ProductGridQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    issues: list[ProductGridQualityIssue] = Field(default_factory=list)


class ProductSignalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[ProductSignal] = Field(default_factory=list)
    item_candidates: list[ProductItemCandidate] = Field(default_factory=list)
    product_visual_evidence: list[ProductVisualEvidence] = Field(default_factory=list)
    associations: list[ProductToContentAssociation] = Field(default_factory=list)
    grid_quality: Optional[ProductGridQualityReport] = None


ProductSignalReportPayload = ProductSignalReport


VERIFICATION_REPORT_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.verification_report"
VERIFICATION_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"


class VerificationOverallStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class VerificationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    supported: bool


class VerificationReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[VerificationClaim]
    overall_status: VerificationOverallStatus


OUTPUT_QUALITY_REPORT_SCHEMA_NAME: Final[str] = "feedfoundry.outputs.output_quality_report"
OUTPUT_QUALITY_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"


class OutputQualityReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


SCHEMA_REGISTRY: dict[tuple[str, str], Type[BaseModel]] = {
    (FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION): FactsheetPayload,
    (FAQ_SCHEMA_NAME, FAQ_SCHEMA_VERSION): FAQPayload,
    (CHAPTERS_SCHEMA_NAME, CHAPTERS_SCHEMA_VERSION): ChaptersPayload,
    (METADATA_SCHEMA_NAME, METADATA_SCHEMA_VERSION): MetadataPayload,
    (CTA_SCHEMA_NAME, CTA_SCHEMA_VERSION): CTAPayload,
    (
        HOSTED_MANIFEST_ENRICHMENT_SCHEMA_NAME,
        HOSTED_MANIFEST_ENRICHMENT_SCHEMA_VERSION,
    ): HostedManifestEnrichmentPayload,
    (VISUAL_ANALYSIS_REPORT_SCHEMA_NAME, VISUAL_ANALYSIS_REPORT_SCHEMA_VERSION): VisualAnalysisReport,
    (PRODUCT_SIGNAL_REPORT_SCHEMA_NAME, PRODUCT_SIGNAL_REPORT_SCHEMA_VERSION): ProductSignalReport,
    (VERIFICATION_REPORT_SCHEMA_NAME, VERIFICATION_REPORT_SCHEMA_VERSION): VerificationReportPayload,
    (OUTPUT_QUALITY_REPORT_SCHEMA_NAME, OUTPUT_QUALITY_REPORT_SCHEMA_VERSION): OutputQualityReportPayload,
}
