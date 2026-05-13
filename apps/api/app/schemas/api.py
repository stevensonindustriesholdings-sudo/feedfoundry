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
    allowed: bool = True
    warning: bool = False
    message: Optional[str] = None
    available_minutes: Optional[int] = None
    estimated_minutes: int
    goodwill_minutes: Optional[int] = None
    # Legacy field names — values are processing minutes (same integer as estimated_minutes).
    estimated_credits: int
    reserved_credits: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: int
    current_stage: Optional[str]
    estimated_credits: Optional[int]
    reserved_credits: Optional[int]
    actual_credits_so_far: Optional[int] = None
    goodwill_minutes_granted: Optional[int] = None
    estimated_processing_minutes: Optional[int] = None
    reserved_processing_minutes: Optional[int] = None
    processing_minutes_used_so_far: Optional[int] = None


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
    processing_minutes_used_lifetime: int
    goodwill_processing_minutes_granted_ytd: int
    next_processing_period_end: Optional[str]
    # Deprecated mirrors for older clients — same values as processing_minutes_*.
    credits_available: int
    credits_reserved: int
    credits_spent_lifetime: int
    next_credit_expiry: Optional[str]
