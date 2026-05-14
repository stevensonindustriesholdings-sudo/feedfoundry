"""Bounded OpenAI Responses adapter — httpx fully mocked (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ai.canary_error_codes import CanaryFailClosedCode, CanaryRuntimeCode
from ai.openai_adapter import OpenAIHTTPAdapterError, OpenAIStructuredProviderShell
from ai.provider_mode import ProviderDisabledError
from ai.schemas.output_contracts import (
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    P7_CANARY_LIVE_SCHEMA_NAME,
    P7_CANARY_LIVE_SCHEMA_VERSION,
)
from ai.types import AICompletionRequest


def _factsheet_request() -> AICompletionRequest:
    return AICompletionRequest(
        stage_name="test_stage",
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        prompt_version="pv1",
        model="gpt-4.1-mini",
        input_bundle={"chunk_index": 0, "transcript_text": "hello", "segment_id": "s1"},
        max_tokens=128,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id="trace:adapter:test",
    )


def _p7_canary_request() -> AICompletionRequest:
    return AICompletionRequest(
        stage_name="test_stage",
        schema_name=P7_CANARY_LIVE_SCHEMA_NAME,
        schema_version=P7_CANARY_LIVE_SCHEMA_VERSION,
        prompt_version="pv1",
        model="gpt-4.1-mini",
        input_bundle={"chunk_index": 0, "transcript_text": "hello", "segment_id": "s1"},
        max_tokens=128,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id="trace:adapter:test",
    )


def _canary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_ENABLE_REAL_PROVIDER", "true")
    monkeypatch.setenv("AI_CANARY_MAX_CALLS", "2")
    monkeypatch.setenv("AI_CANARY_MAX_COST", "0.5")
    monkeypatch.setenv("AI_CANARY_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")


def _mock_client_cm(inner: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None
    return cm


def test_complete_fail_closed_without_runner_flag(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.delenv("FF_OPENAI_CANARY_RUNNER_ENABLED", raising=False)
    monkeypatch.delenv("FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE", raising=False)
    shell = OpenAIStructuredProviderShell()
    with pytest.raises(ProviderDisabledError, match=CanaryFailClosedCode.CANARY_RUNNER_FLAG_OFF.value):
        shell.complete(_factsheet_request())


def test_complete_http_unlocked_by_enrichment_live_without_runner(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("AI_STRUCTURED_PROVIDER_MODE", "canary_openai")
    monkeypatch.delenv("FF_OPENAI_CANARY_RUNNER_ENABLED", raising=False)
    monkeypatch.setenv("FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE", "true")
    body = {"title": "T", "summary": "S", "key_facts": ["a"]}
    api_json = {
        "id": "resp_enrichment_gate_1",
        "object": "response",
        "status": "completed",
        "model": "gpt-4.1-mini",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(body)}],
            }
        ],
        "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
    }
    inner = MagicMock()
    inner.post.return_value = httpx.Response(200, json=api_json)
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        resp = shell.complete(_factsheet_request())
    assert resp.parsed_json == body
    inner.post.assert_called_once()
    _, kwargs = inner.post.call_args
    assert kwargs["json"]["text"]["format"]["schema"].get("title") == "P7CanaryFactsheetLivePayload"


def test_complete_success_parses_usage_and_output(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    body = {
        "title": "T",
        "summary": "S",
        "key_facts": ["a"],
    }
    api_json = {
        "id": "resp_fixture_1",
        "object": "response",
        "status": "completed",
        "model": "gpt-4.1-mini",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(body)}],
            }
        ],
        "usage": {"input_tokens": 9, "output_tokens": 11, "total_tokens": 20},
    }
    inner = MagicMock()
    inner.post.return_value = httpx.Response(200, json=api_json)
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        resp = shell.complete(_p7_canary_request())
    assert resp.parsed_json == body
    assert resp.provider_request_id == "resp_fixture_1"
    assert resp.input_tokens == 9
    assert resp.output_tokens == 11
    assert resp.provider_name == "openai"
    inner.post.assert_called_once()
    args, kwargs = inner.post.call_args
    assert str(args[0]).rstrip("/").endswith("/v1/responses")
    assert kwargs["json"]["model"] == "gpt-4.1-mini"
    assert kwargs["json"]["text"]["format"]["type"] == "json_schema"
    assert kwargs["json"]["text"]["format"]["name"]
    assert kwargs["json"]["text"]["format"]["schema"].get("title") == "P7CanaryFactsheetLivePayload"


def test_http_400_maps_and_includes_redacted_error(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    inner = MagicMock()
    inner.post.return_value = httpx.Response(
        400,
        json={
            "id": "resp_err_1",
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_json_schema",
                "param": "text.format.schema",
                "message": "Invalid schema: example detail truncated in production.",
            },
        },
    )
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        with pytest.raises(OpenAIHTTPAdapterError) as ei:
            shell.complete(_p7_canary_request())
    assert ei.value.code == CanaryRuntimeCode.HTTP_BAD_REQUEST.value
    assert "invalid_request_error" in str(ei.value)
    assert "invalid_json_schema" in str(ei.value)


def test_http_401_maps_to_stable_code(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    inner = MagicMock()
    inner.post.return_value = httpx.Response(401, json={"error": {"message": "bad"}})
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        with pytest.raises(OpenAIHTTPAdapterError) as ei:
            shell.complete(_factsheet_request())
    assert ei.value.code == CanaryRuntimeCode.HTTP_AUTH.value


def test_http_429_rate_limit(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    inner = MagicMock()
    inner.post.return_value = httpx.Response(429, json={})
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        with pytest.raises(OpenAIHTTPAdapterError) as ei:
            shell.complete(_factsheet_request())
    assert ei.value.code == CanaryRuntimeCode.HTTP_RATE_LIMIT.value


def test_http_timeout(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    inner = MagicMock()
    inner.post.side_effect = httpx.TimeoutException("timeout")
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        with pytest.raises(OpenAIHTTPAdapterError) as ei:
            shell.complete(_factsheet_request())
    assert ei.value.code == CanaryRuntimeCode.HTTP_TIMEOUT.value


def test_malformed_json_body(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    inner = MagicMock()
    inner.post.return_value = httpx.Response(200, text="not-json")
    with patch("ai.openai_adapter.httpx.Client", return_value=_mock_client_cm(inner)):
        shell = OpenAIStructuredProviderShell()
        with pytest.raises(OpenAIHTTPAdapterError) as ei:
            shell.complete(_factsheet_request())
    assert ei.value.code == CanaryRuntimeCode.HTTP_MALFORMED.value


def test_unknown_schema_raises(monkeypatch: pytest.MonkeyPatch):
    _canary_env(monkeypatch)
    monkeypatch.setenv("FF_OPENAI_CANARY_RUNNER_ENABLED", "true")
    req = AICompletionRequest(
        stage_name="x",
        schema_name="unknown.schema",
        schema_version="0.0.0",
        prompt_version="p",
        model="gpt-4.1-mini",
        input_bundle={},
        max_tokens=32,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id="t",
    )
    shell = OpenAIStructuredProviderShell()
    with pytest.raises(OpenAIHTTPAdapterError) as ei:
        shell.complete(req)
    assert ei.value.code == CanaryRuntimeCode.SCHEMA_NOT_REGISTERED.value
