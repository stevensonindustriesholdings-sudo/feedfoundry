from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "feedfoundry-api"
    version: str = "0.1.0"


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int = Field(ge=1)
    media_type: str


class PresignUploadResponse(BaseModel):
    media_asset_id: str
    upload_url: str
    storage_key: str
    expires_in_seconds: int = 900


class CreateJobRequest(BaseModel):
    media_asset_id: str
    requested_outputs: List[str]
    distribution_targets: Optional[List[str]] = None


class CreateJobResponse(BaseModel):
    """Job created; estimated and reserved **processing minutes** (ledger unit)."""

    job_id: str
    status: str
    estimated_processing_minutes: int
    reserved_processing_minutes: int
    estimated_processing_hours: float = Field(
        description="Rounded hours equivalent of the estimate (display helper).",
    )
    # Deprecated legacy aliases preserved one release for older clients.
    estimated_credits: Optional[int] = Field(
        default=None,
        deprecated=True,
        description="Alias of estimated_processing_minutes for legacy clients.",
    )
    reserved_credits: Optional[int] = Field(
        default=None,
        deprecated=True,
        description="Alias of reserved_processing_minutes for legacy clients.",
    )


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: int
    current_stage: Optional[str]
    estimated_processing_minutes: Optional[int] = None
    reserved_processing_minutes: Optional[int] = None
    actual_processing_minutes_charged: Optional[int] = None
    estimated_processing_hours: Optional[float] = None
    # Deprecated legacy aliases preserved one release for older clients.
    estimated_credits: Optional[int] = Field(default=None, deprecated=True)
    reserved_credits: Optional[int] = Field(default=None, deprecated=True)
    actual_credits_so_far: Optional[int] = Field(default=None, deprecated=True)


class JobSummaryItem(BaseModel):
    job_id: str
    status: str
    progress_percent: int
    current_stage: Optional[str] = None
    media_asset_id: str
    created_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobSummaryItem]


class OutputItemResponse(BaseModel):
    type: str
    title: str
    format: str
    download_url: str


class JobOutputsResponse(BaseModel):
    job_id: str
    outputs: List[OutputItemResponse]


class AccountProcessingBalanceResponse(BaseModel):
    """Annual hosted archive + remaining **processing minutes** (wallet balance)."""

    annual_archive_access_status: str
    hosting_until: Optional[str]
    processing_minutes_available: int
    processing_minutes_reserved: int
    processing_minutes_used_lifetime: int
    processing_period_ends_on: Optional[str] = None
    processing_hours_available: float = Field(
        description="Hours equivalent of available minutes (display helper).",
    )
    # Deprecated legacy field names preserved one release for older consumers.
    credits_available: Optional[int] = Field(default=None, deprecated=True)
    credits_reserved: Optional[int] = Field(default=None, deprecated=True)
    credits_spent_lifetime: Optional[int] = Field(default=None, deprecated=True)
    next_credit_expiry: Optional[str] = Field(default=None, deprecated=True)


# Compatibility alias for older imports; canonical name above.
AccountCreditsResponse = AccountProcessingBalanceResponse


class CatalogOutputKind(BaseModel):
    slug: str
    title: str
    description: str


class OutputCatalogResponse(BaseModel):
    """
    Contract for requested job outputs vs persisted ``job_outputs`` rows.

    Worker may not emit every persisted type for every job; clients should list
    ``GET /v1/jobs/{id}/outputs`` for concrete artifacts.
    """

    requested_output_kinds: List[CatalogOutputKind]
    persisted_output_types: List[CatalogOutputKind]
    notes: str = (
        "Request slugs (e.g. transcript) map to stored types (e.g. raw_transcript) in the worker; "
        "see OpenAPI descriptions on POST /v1/jobs."
    )
