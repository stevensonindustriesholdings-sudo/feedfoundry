"""Redacted read models for internal AI run visibility (admin / ops only)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AIStageVisibilityOut(BaseModel):
    """Single stage row — no ``extra_json`` or raw prompts."""

    id: str
    stage_name: str
    status: str
    provider_name: Optional[str] = None
    model_name: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input_tokens: int = Field(0, description="Reported or estimated input token count for this stage.")
    output_tokens: int = Field(0, description="Reported or estimated output token count for this stage.")
    cost_estimate_internal: Optional[float] = Field(
        None,
        description="Internal rough cost estimate (arbitrary units); not customer-facing billing.",
    )
    validation_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    provider_request_id: Optional[str] = None
    created_at: datetime


class AIRunVisibilityOut(BaseModel):
    """One AI run with nested stages — safe for internal dashboards only."""

    id: str
    job_id: str
    organisation_id: str
    status: str
    provider_mode: Optional[str] = Field(
        None,
        description="Inferred from persisted stage provider names when available (e.g. mock, openai); "
        "``mixed`` if stages disagree.",
    )
    captain_plan_version: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    stage_count: int = Field(..., description="Number of stage log rows attached to this run.")
    stages: List[AIStageVisibilityOut] = Field(default_factory=list)


class AIRunListEnvelope(BaseModel):
    ai_runs: List[AIRunVisibilityOut]
    count: int
