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
    job_id: str
    status: str
    estimated_processing_minutes: int
    reserved_processing_minutes: int
    estimated_credits: int = Field(
        deprecated=True,
        description="Alias of estimated_processing_minutes for legacy clients.",
    )
    reserved_credits: int = Field(
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
    estimated_credits: Optional[int] = Field(default=None, deprecated=True)
    reserved_credits: Optional[int] = Field(default=None, deprecated=True)
    actual_credits_so_far: Optional[int] = Field(default=None, deprecated=True)


class OutputItemResponse(BaseModel):
    type: str
    title: str
    format: str
    download_url: str


class JobOutputsResponse(BaseModel):
    job_id: str
    outputs: List[OutputItemResponse]


class AccountCreditsResponse(BaseModel):
    annual_access_status: str
    hosting_until: Optional[str]
    processing_minutes_available: int
    processing_minutes_reserved: int
    processing_minutes_spent_lifetime: int
    next_processing_period_end: Optional[str] = Field(
        default=None,
        description="Calendar end of current annual access period (processing allowance anchor).",
    )
    credits_available: int = Field(deprecated=True)
    credits_reserved: int = Field(deprecated=True)
    credits_spent_lifetime: int = Field(deprecated=True)
    next_credit_expiry: Optional[str] = Field(default=None, deprecated=True)
