from __future__ import annotations

from pathlib import Path

import pytest

from app.services import ai_internal_policy as policy


def test_internal_policy_module_does_not_import_credit_ledger():
    assert "credit_ledger" not in policy.__dict__
    src = Path(policy.__file__).read_text(encoding="utf-8")
    assert "credit_ledger" not in src


def test_job_cap_helpers_respect_policy():
    caps = policy.InternalJobAICapPolicy(
        max_internal_spend_units_per_job=10.0,
        max_structured_calls_per_job=3,
    )
    assert policy.job_internal_spend_within_cap(accumulated_internal_units=5.0, policy=caps)
    assert not policy.job_internal_spend_within_cap(accumulated_internal_units=11.0, policy=caps)
    assert policy.job_structured_calls_within_cap(calls_completed=3, policy=caps)
    assert not policy.job_structured_calls_within_cap(calls_completed=4, policy=caps)


def test_org_window_cap():
    org = policy.InternalOrgAICapPolicy(max_internal_spend_units_per_window=100.0, window_seconds=3600)
    assert policy.org_window_units_within_cap(window_accumulated_internal_units=50.0, policy=org)
    assert not policy.org_window_units_within_cap(window_accumulated_internal_units=101.0, policy=org)


def test_circuit_breaker_flags():
    state = policy.CircuitBreakerState(failure_threshold=2, consecutive_failures=2)
    assert policy.circuit_breaker_should_trip(state)
    opened = state.model_copy(
        update={
            "status": policy.CircuitBreakerStatus.OPEN,
            "opened_at_epoch_ms": 1_000_000,
        }
    )
    assert policy.circuit_breaker_should_half_open(state=opened, now_epoch_ms=1_000_000 + 120_000)


def test_merge_rate_limit_snapshots_prefers_tightest_budget():
    a = policy.RateLimitBudgetSnapshot(remaining_requests=10, reset_epoch_ms=200, retry_after_seconds=1)
    b = policy.RateLimitBudgetSnapshot(remaining_requests=3, reset_epoch_ms=100, retry_after_seconds=5)
    merged = policy.merge_rate_limit_snapshots([a, b])
    assert merged.remaining_requests == 3
    assert merged.reset_epoch_ms == 100
    assert merged.retry_after_seconds == 5


def test_ai_run_blob_key_prefix_normalizes():
    assert policy.ai_run_blob_key_prefix("org/x", "//ai-runs/", "job-1") == "org/x/ai-runs/job-1"


def test_load_internal_ai_policy_bundle_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FF_INTERNAL_AI_MAX_UNITS_PER_JOB", "42")
    monkeypatch.setenv("FF_INTERNAL_AI_MAX_CALLS_PER_JOB", "7")
    bundle = policy.load_internal_ai_policy_bundle_from_env()
    assert bundle.per_job.max_internal_spend_units_per_job == 42.0
    assert bundle.per_job.max_structured_calls_per_job == 7
