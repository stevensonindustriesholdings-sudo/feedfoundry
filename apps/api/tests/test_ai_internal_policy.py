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


def test_load_ai_canary_gate_config_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "1")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "5")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "30")
    cfg = policy.load_ai_canary_gate_config_from_env()
    assert cfg.canary_enabled is True
    assert cfg.real_provider_enabled is True
    assert cfg.max_calls == 5
    assert cfg.max_cost == 0.5
    assert cfg.timeout_seconds == 30


def test_ai_canary_numeric_gates_satisfied():
    ok = policy.AICanaryGateConfig(
        canary_enabled=True,
        real_provider_enabled=True,
        max_calls=1,
        max_cost=0.01,
        timeout_seconds=10,
    )
    assert policy.ai_canary_numeric_gates_satisfied(ok)
    bad = ok.model_copy(update={"max_calls": 0})
    assert not policy.ai_canary_numeric_gates_satisfied(bad)
    bad_cost = ok.model_copy(update={"max_cost": 0.0})
    assert not policy.ai_canary_numeric_gates_satisfied(bad_cost)


def test_ai_canary_booleans_allow_real_path():
    off = policy.AICanaryGateConfig(canary_enabled=False, real_provider_enabled=True)
    assert not policy.ai_canary_booleans_allow_real_path(off)
    on = policy.AICanaryGateConfig(canary_enabled=True, real_provider_enabled=True)
    assert policy.ai_canary_booleans_allow_real_path(on)


def test_ai_provider_allows_openai_structured_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert policy.ai_provider_allows_openai_structured_path()
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    assert not policy.ai_provider_allows_openai_structured_path()


def test_ai_provider_empty_not_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert not policy.ai_provider_allows_openai_structured_path()


def test_structured_openai_canary_policy_allows_http_requires_both_booleans(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "1")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.01")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "false")
    assert not policy.structured_openai_canary_policy_allows_http_preconditions()
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_ENABLED", "false")
    assert not policy.structured_openai_canary_policy_allows_http_preconditions()


def test_structured_openai_canary_policy_requires_openai_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "1")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.01")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    assert not policy.structured_openai_canary_policy_allows_http_preconditions()
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert policy.structured_openai_canary_policy_allows_http_preconditions()


def test_structured_openai_canary_policy_decimal_cost_allowed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "1")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.0001")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert policy.structured_openai_canary_policy_allows_http_preconditions()


def test_structured_openai_canary_policy_max_cost_zero_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "1")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert not policy.structured_openai_canary_policy_allows_http_preconditions()


def test_structured_openai_canary_policy_timeout_zero_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "1")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.01")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert not policy.structured_openai_canary_policy_allows_http_preconditions()


def test_structured_openai_canary_http_preconditions_has_no_ledger_import():
    import inspect

    src = inspect.getsource(policy.structured_openai_canary_policy_allows_http_preconditions)
    assert "credit_ledger" not in src
