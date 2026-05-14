"""Internal ops-only AI cost, cap, and backoff policy helpers.

These structures govern **engineering / ops** spend and safety — not customer
processing-minute wallets, Stripe units, or any customer-visible “credits”.

Storage portability: AI run artifacts (JSONL, stage blobs) should use the same
S3-compatible layout as the rest of FeedFoundry (``source/``, ``outputs/``,
``ai-runs/{job_id}/…`` under the org bucket prefix). Keys are opaque server-side
paths; never embed secrets or presigned query strings in persisted manifests.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Iterable, Optional

from pydantic import BaseModel, Field


class CircuitBreakerStatus(str, Enum):
    """Governor-style circuit breaker position (data only — no I/O)."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerState(BaseModel):
    """Mutable-style snapshot of breaker math; callers persist/update as needed."""

    status: CircuitBreakerStatus = CircuitBreakerStatus.CLOSED
    consecutive_failures: int = Field(default=0, ge=0)
    failure_threshold: int = Field(default=5, ge=1)
    success_threshold_half_open: int = Field(default=1, ge=1)
    opened_at_epoch_ms: Optional[int] = None
    cooldown_seconds: int = Field(default=60, ge=1)


class RateLimitBudgetSnapshot(BaseModel):
    """Structured view of provider rate-limit metadata after a call (no HTTP here)."""

    limit_requests: Optional[int] = None
    remaining_requests: Optional[int] = None
    reset_epoch_ms: Optional[int] = None
    retry_after_seconds: Optional[int] = None
    policy_documents: Optional[str] = None


class InternalJobAICapPolicy(BaseModel):
    """Hard-ish caps for a single job’s internal AI spend surface (ops metrics)."""

    max_internal_spend_units_per_job: float = Field(default=1_000_000.0, ge=0.0)
    max_structured_calls_per_job: int = Field(default=500, ge=1)


class InternalOrgAICapPolicy(BaseModel):
    """Rolling-window guard for org-wide internal AI fan-out (structure only)."""

    max_internal_spend_units_per_window: float = Field(default=1_000_000_000.0, ge=0.0)
    window_seconds: int = Field(default=86_400, ge=60)


class InternalAIPolicyBundle(BaseModel):
    """Aggregate config blob loaded from env + static defaults."""

    per_job: InternalJobAICapPolicy = Field(default_factory=InternalJobAICapPolicy)
    per_org: InternalOrgAICapPolicy = Field(default_factory=InternalOrgAICapPolicy)


class AICanaryGateConfig(BaseModel):
    """Ops-only canary caps for real provider paths (engineering controls; not customer credits).

    **Mode matrix** (see ``docs/phase7-openai-canary.md``):

    - ``mock`` — default; no real HTTP; ignores these booleans for routing.
    - ``canary`` — real adapter may run **only** when ``AI_CANARY_ENABLED`` and
      ``AI_ENABLE_REAL_PROVIDER`` are truthy, ``OPENAI_API_KEY`` is non-empty (checked
      in the worker), and numeric caps parse as valid positive bounds.
    - ``disabled`` — structured real path is off; worker returns a fail-closed provider.

    Env vars (placeholders in ``.env.example``; never commit secrets):

    - ``AI_CANARY_ENABLED`` — master canary toggle.
    - ``AI_ENABLE_REAL_PROVIDER`` — kill-switch; must be true for any real SDK path.
    - ``AI_CANARY_MAX_CALLS`` — hard cap hint for orchestration (must be >= 1 when canary on).
    - ``AI_CANARY_MAX_COST`` — internal cost ceiling for canary (>= 0).
    - ``AI_CANARY_TIMEOUT_SECONDS`` — per-call timeout bound (> 0).
    """

    canary_enabled: bool = False
    real_provider_enabled: bool = False
    max_calls: int = Field(default=0, ge=0)
    max_cost: float = Field(default=0.0, ge=0.0)
    timeout_seconds: int = Field(default=0, ge=0)


def ai_run_blob_key_prefix(*segments: str) -> str:
    """Return a normalized slash key prefix for AI run blobs (no secrets)."""

    cleaned = [s.strip("/") for s in segments if s and s.strip("/")]
    return "/".join(cleaned)


def load_internal_ai_policy_bundle_from_env() -> InternalAIPolicyBundle:
    """Hydrate caps from optional ``FF_INTERNAL_AI_*`` env vars (empty → defaults)."""

    def _f(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        return float(raw)

    def _i(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        return int(raw)

    per_job = InternalJobAICapPolicy(
        max_internal_spend_units_per_job=_f("FF_INTERNAL_AI_MAX_UNITS_PER_JOB", 1_000_000.0),
        max_structured_calls_per_job=_i("FF_INTERNAL_AI_MAX_CALLS_PER_JOB", 500),
    )
    per_org = InternalOrgAICapPolicy(
        max_internal_spend_units_per_window=_f(
            "FF_INTERNAL_AI_ORG_WINDOW_MAX_UNITS", 1_000_000_000.0
        ),
        window_seconds=_i("FF_INTERNAL_AI_ORG_WINDOW_SECONDS", 86_400),
    )
    return InternalAIPolicyBundle(per_job=per_job, per_org=per_org)


def _truthy_env(name: str) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_ai_canary_gate_config_from_env() -> AICanaryGateConfig:
    """Parse canary / kill-switch env. Missing numerics default to zero (fail-closed for canary)."""

    def _i(name: str, default: int = 0) -> int:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        return int(raw)

    def _f(name: str, default: float = 0.0) -> float:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        return float(raw)

    return AICanaryGateConfig(
        canary_enabled=_truthy_env("AI_CANARY_ENABLED"),
        real_provider_enabled=_truthy_env("AI_ENABLE_REAL_PROVIDER"),
        max_calls=_i("AI_CANARY_MAX_CALLS", 0),
        max_cost=_f("AI_CANARY_MAX_COST", 0.0),
        timeout_seconds=_i("AI_CANARY_TIMEOUT_SECONDS", 0),
    )


def ai_canary_numeric_gates_satisfied(cfg: AICanaryGateConfig) -> bool:
    """Structured canary requires explicit positive bounds (zero defaults = closed)."""

    return cfg.max_calls >= 1 and cfg.max_cost > 0.0 and cfg.timeout_seconds >= 1


def ai_canary_booleans_allow_real_path(cfg: AICanaryGateConfig) -> bool:
    """Both the canary lane and the real-provider kill-switch must be on."""

    return cfg.canary_enabled and cfg.real_provider_enabled


def job_internal_spend_within_cap(
    *,
    accumulated_internal_units: float,
    policy: InternalJobAICapPolicy,
) -> bool:
    return 0.0 <= accumulated_internal_units <= policy.max_internal_spend_units_per_job


def job_structured_calls_within_cap(*, calls_completed: int, policy: InternalJobAICapPolicy) -> bool:
    """``calls_completed`` is the count after a stage finishes (must be ≤ max)."""

    return 0 <= calls_completed <= policy.max_structured_calls_per_job


def org_window_units_within_cap(
    *,
    window_accumulated_internal_units: float,
    policy: InternalOrgAICapPolicy,
) -> bool:
    return 0.0 <= window_accumulated_internal_units <= policy.max_internal_spend_units_per_window


def circuit_breaker_should_trip(state: CircuitBreakerState) -> bool:
    return state.consecutive_failures >= state.failure_threshold


def circuit_breaker_should_half_open(
    *,
    state: CircuitBreakerState,
    now_epoch_ms: int,
) -> bool:
    if state.status != CircuitBreakerStatus.OPEN:
        return False
    if state.opened_at_epoch_ms is None:
        return True
    elapsed_s = max(0, (now_epoch_ms - state.opened_at_epoch_ms) / 1000.0)
    return elapsed_s >= float(state.cooldown_seconds)


def merge_rate_limit_snapshots(snapshots: Iterable[RateLimitBudgetSnapshot]) -> RateLimitBudgetSnapshot:
    """Pick the most conservative remaining budget across a batch (ops helper)."""

    merged = RateLimitBudgetSnapshot()
    min_remaining: Optional[int] = None
    min_reset: Optional[int] = None
    max_retry: Optional[int] = None
    for snap in snapshots:
        if snap.remaining_requests is not None:
            min_remaining = (
                snap.remaining_requests
                if min_remaining is None
                else min(min_remaining, snap.remaining_requests)
            )
        if snap.reset_epoch_ms is not None:
            min_reset = (
                snap.reset_epoch_ms if min_reset is None else min(min_reset, snap.reset_epoch_ms)
            )
        if snap.retry_after_seconds is not None:
            max_retry = (
                snap.retry_after_seconds
                if max_retry is None
                else max(max_retry, snap.retry_after_seconds)
            )
        merged.limit_requests = snap.limit_requests or merged.limit_requests
        merged.policy_documents = snap.policy_documents or merged.policy_documents
    merged.remaining_requests = min_remaining
    merged.reset_epoch_ms = min_reset
    merged.retry_after_seconds = max_retry
    return merged
