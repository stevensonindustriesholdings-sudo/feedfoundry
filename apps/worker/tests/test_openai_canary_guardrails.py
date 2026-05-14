"""OpenAI canary guardrails: mock default, fail-closed canary, no live HTTP in tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai.provider_mode import ProviderDisabledError, StructuredProviderMode, resolve_structured_provider_mode
from ai.registry import get_structured_ai_provider
from ai.types import AICompletionRequest


def _minimal_request() -> AICompletionRequest:
    return AICompletionRequest(
        stage_name="transcript_intelligence",
        schema_name="ai.stub.v1",
        schema_version="0.1.0",
        prompt_version="p1",
        model="gpt-4.1-mini",
        input_bundle={"hello": "world"},
        max_tokens=32,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.01,
        trace_id="job:canary:test",
    )


def test_mock_mode_even_if_canary_flags_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-be-used")
    prov = get_structured_ai_provider()
    assert prov.name == "mock"


def test_canary_without_openai_key_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "3")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.25")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "60")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderDisabledError, match="OPENAI_API_KEY"):
        get_structured_ai_provider()


def test_canary_canary_master_off_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    monkeypatch.setenv("AI_CANARY_ENABLED", "false")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.1")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    with pytest.raises(ProviderDisabledError, match="AI_CANARY_ENABLED"):
        get_structured_ai_provider()


def test_canary_numeric_defaults_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.delenv("AI_CANARY_MAX_CALLS", raising=False)
    monkeypatch.delenv("AI_CANARY_MAX_COST", raising=False)
    monkeypatch.delenv("AI_CANARY_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    with pytest.raises(ProviderDisabledError, match="AI_CANARY_MAX"):
        get_structured_ai_provider()


def test_canary_all_gates_returns_shell_runtime_on_complete(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    prov = get_structured_ai_provider()
    assert prov.name == "openai"
    with pytest.raises(RuntimeError, match="shell"):
        prov.complete(_minimal_request())


def test_resolve_mode_invalid_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "production")
    with pytest.raises(ProviderDisabledError, match="Invalid AI_STRUCTURED_PROVIDER_MODE"):
        resolve_structured_provider_mode()


def test_openai_adapter_module_has_no_sdk_imports():
    root = Path(__file__).resolve().parents[1] / "ai" / "openai_adapter.py"
    text = root.read_text(encoding="utf-8")
    assert "httpx" not in text
    assert "import openai" not in text
    assert "from openai" not in text


def test_get_structured_does_not_invoke_httpx(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "mock")
    with patch("httpx.Client") as client_ctor:
        prov = get_structured_ai_provider()
        assert prov.name == "mock"
        client_ctor.assert_not_called()


def test_enum_values_documented():
    assert StructuredProviderMode.MOCK.value == "mock"
    assert StructuredProviderMode.CANARY.value == "canary"
    assert StructuredProviderMode.DISABLED.value == "disabled"
