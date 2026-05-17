from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class AnnualAccessStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    GRACE = "grace"
    SUSPENDED = "suspended"


class CreditTransactionType(str, Enum):
    """Internal ledger line types (amounts are whole processing minutes)."""

    PURCHASE = "purchase"
    ANNUAL_GRANT = "annual_grant"
    RESERVE = "reserve"
    DEBIT = "debit"
    RELEASE = "release"
    REFUND = "refund"
    EXPIRE = "expire"
    VOUCHER_CONVERSION = "voucher_conversion"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    PODCAST = "podcast"
    SHORT_VIDEO = "short_video"
    OTHER = "other"


class MediaAssetStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class JobStatus(str, Enum):
    """Customer-visible job lifecycle (pipeline detail lives in ``current_stage``)."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobOutputType(str, Enum):
    RAW_TRANSCRIPT = "raw_transcript"
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
    MEDIA_INSPECTION = "media_inspection"


class Organisation(SQLModel, table=True):
    __tablename__ = "organisations"

    id: str = Field(default_factory=lambda: new_id("org"), primary_key=True)
    name: str
    slug: Optional[str] = Field(default=None, unique=True, index=True)
    owner_user_id: Optional[str] = None  # users.id (no FK to avoid org↔user cycle on create_all)
    stripe_customer_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: new_id("user"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id")
    email: str = Field(index=True)
    role: UserRole = Field(default=UserRole.MEMBER)
    base44_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AnnualAccess(SQLModel, table=True):
    __tablename__ = "annual_access"

    id: str = Field(default_factory=lambda: new_id("aa"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    plan_code: str
    status: AnnualAccessStatus = Field(default=AnnualAccessStatus.ACTIVE)
    period_start: datetime
    period_end: datetime
    hosting_until: datetime
    included_processing_minutes_annual: int = 0
    stripe_checkout_session_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CreditWallet(SQLModel, table=True):
    """Wallet row: integer **whole processing minutes** (internal ledger, not customer “credits”)."""

    __tablename__ = "credit_wallets"
    __table_args__ = (UniqueConstraint("organisation_id", name="uq_wallet_org"),)

    id: str = Field(default_factory=lambda: new_id("wal"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    processing_minutes_available: int = 0
    processing_minutes_reserved: int = 0
    processing_minutes_spent_lifetime: int = 0
    processing_minutes_expired_lifetime: int = 0
    currency: str = Field(default="FF_PROCESSING_MINUTE")
    updated_at: datetime = Field(default_factory=utcnow)


class CreditTransaction(SQLModel, table=True):
    __tablename__ = "credit_transactions"

    id: str = Field(default_factory=lambda: new_id("ctx"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    wallet_id: str = Field(foreign_key="credit_wallets.id", index=True)
    job_id: Optional[str] = Field(default=None, foreign_key="jobs.id", index=True)
    type: CreditTransactionType
    amount: int
    processing_minutes_available_after: int
    memo: Optional[str] = None
    expires_at: Optional[datetime] = None
    stripe_reference: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class MediaAsset(SQLModel, table=True):
    __tablename__ = "media_assets"

    id: str = Field(default_factory=lambda: new_id("ma"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    uploaded_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    original_filename: str
    media_type: MediaType
    upload_content_type: Optional[str] = Field(default=None, max_length=255)
    storage_source_key: str
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    ffprobe_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    status: MediaAssetStatus = Field(default=MediaAssetStatus.UPLOADED)
    creator_slug: Optional[str] = Field(default=None, index=True)
    asset_slug: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_org_status", "organisation_id", "status"),)

    id: str = Field(default_factory=lambda: new_id("job"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    media_asset_id: str = Field(foreign_key="media_assets.id", index=True)
    media_kind: MediaType = Field(default=MediaType.OTHER)
    source_content_type: Optional[str] = Field(default=None, max_length=255)
    status: JobStatus = Field(default=JobStatus.UPLOADED)
    requested_outputs_json: List[Any] = Field(default_factory=list, sa_column=Column(JSON))
    distribution_targets_json: List[Any] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    progress_percent: int = 0
    current_stage: Optional[str] = None
    estimated_processing_minutes: Optional[int] = None
    reserved_processing_minutes: Optional[int] = None
    actual_processing_minutes_charged: Optional[int] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_message: Optional[str] = None
    error_log_storage_key: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobOutput(SQLModel, table=True):
    __tablename__ = "job_outputs"
    __table_args__ = (Index("ix_job_outputs_job_type", "job_id", "output_type"),)

    id: str = Field(default_factory=lambda: new_id("out"), primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    output_type: JobOutputType
    schema_version: str = Field(default="1.0", max_length=16)
    storage_key: Optional[str] = None
    json_payload: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    markdown_payload: Optional[str] = None
    html_payload: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)


class AIUsageLog(SQLModel, table=True):
    __tablename__ = "ai_usage_logs"

    id: str = Field(default_factory=lambda: new_id("aiu"), primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    module_name: str
    provider: str
    model: str
    input_tokens_estimated: Optional[int] = None
    output_tokens_estimated: Optional[int] = None
    cost_estimate_usd: Optional[float] = None
    processing_minutes_logged: Optional[int] = None
    latency_ms: Optional[int] = None
    rate_limit_remaining_requests: Optional[int] = None
    rate_limit_remaining_tokens: Optional[int] = None
    status: str
    error_code: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class ProviderConfig(SQLModel, table=True):
    __tablename__ = "provider_configs"

    id: str = Field(default_factory=lambda: new_id("pvc"), primary_key=True)
    provider: str
    model: str
    module_name: str
    enabled: bool = True
    priority: int = 100
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    cost_ceiling_credits: Optional[float] = None
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class YoutubeSourceQueue(SQLModel, table=True):
    """Operator- or customer-submitted public YouTube URLs awaiting a future pipeline."""

    __tablename__ = "youtube_source_queue"
    __table_args__ = (Index("ix_youtube_queue_org_status", "organisation_id", "status"),)

    id: str = Field(default_factory=lambda: new_id("ytq"), primary_key=True)
    organisation_id: str = Field(foreign_key="organisations.id", index=True)
    youtube_url: str = Field(max_length=2048)
    status: str = Field(default="queued", max_length=32)
    notes: Optional[str] = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=utcnow)


class StripeWebhookEvent(SQLModel, table=True):
    """Processed Stripe event ids — duplicate deliveries must not mutate state."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: str = Field(primary_key=True, max_length=255)
    event_type: str = Field(max_length=128)
    outcome: str = Field(default="processed", max_length=64)
    created_at: datetime = Field(default_factory=utcnow)


class WorkerHeartbeat(SQLModel, table=True):
    """Last-seen heartbeat for worker processes (ops visibility, not a queue)."""

    __tablename__ = "worker_heartbeats"

    worker_id: str = Field(primary_key=True, max_length=256)
    last_seen_at: datetime = Field(default_factory=utcnow)
    hostname: str = Field(default="", max_length=256)
    app_env: str = Field(default="", max_length=64)
    git_commit: str = Field(default="", max_length=64)
    build_timestamp: str = Field(default="", max_length=64)
    api_version: str = Field(default="", max_length=32)
