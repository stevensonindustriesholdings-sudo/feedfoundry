"""OpenAI structured provider — bounded HTTP via Responses API (canary, fail-closed)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx

from ai.canary_error_codes import CanaryRuntimeCode
from ai.openai_canary_gates import (
    check_openai_responses_http_gates_or_raise,
    check_openai_structured_adapter_construct_gates_or_raise,
)
from ai.provider import AIProvider
from ai.schemas.output_contracts import SCHEMA_REGISTRY
from ai.types import AICompletionRequest, AICompletionResponse
from app.services.ai_internal_policy import load_ai_canary_gate_config_from_env

log = logging.getLogger("feedfoundry.worker.ai.openai_adapter")


class OpenAIHTTPAdapterError(RuntimeError):
    """Transport or parse failure after canary gates pass (stable ``code`` for ops / AIStageLog)."""

    def __init__(self, message: str, *, code: str, status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _responses_base_url() -> str:
    raw = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com").strip().rstrip("/")
    return raw or "https://api.openai.com"


def _format_schema_name_token(schema_name: str, schema_version: str) -> str:
    combined = f"{schema_name}_{schema_version}".lower()
    slug = re.sub(r"[^a-z0-9_-]+", "_", combined).strip("_") or "schema"
    return slug[:64]


def _json_schema_for_request(req: AICompletionRequest) -> dict[str, Any]:
    key = (req.schema_name, req.schema_version)
    model_cls = SCHEMA_REGISTRY.get(key)
    if model_cls is None:
        raise OpenAIHTTPAdapterError(
            f"No SCHEMA_REGISTRY entry for {req.schema_name!r} {req.schema_version!r}",
            code=CanaryRuntimeCode.SCHEMA_NOT_REGISTERED.value,
        )
    return model_cls.model_json_schema()


def _build_request_payload(req: AICompletionRequest, *, json_schema: dict[str, Any]) -> dict[str, Any]:
    user_text = json.dumps(dict(req.input_bundle), ensure_ascii=False, separators=(",", ":"))
    eff_max_tokens = min(int(req.max_tokens), 8192) if int(req.max_tokens) > 0 else 512
    fmt_name = _format_schema_name_token(req.schema_name, req.schema_version)
    return {
        "model": req.model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are FeedFoundry's structured-output engine. "
                            f"stage={req.stage_name} schema={req.schema_name}@{req.schema_version} "
                            f"prompt_version={req.prompt_version} trace_id={req.trace_id}. "
                            "Respond only with JSON matching the response schema (no markdown)."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
            },
        ],
        "temperature": float(req.temperature),
        "max_output_tokens": eff_max_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": fmt_name,
                "schema": json_schema,
                "strict": True,
            }
        },
        "metadata": {
            "ff_trace_id": req.trace_id[:128],
            "ff_stage": req.stage_name[:64],
        },
    }


def _parse_success_json(data: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    rid_placeholder = str(data.get("id") or "")
    err_obj = data.get("error")
    if err_obj:
        msg = str(err_obj)
        if isinstance(err_obj, dict):
            msg = str(err_obj.get("message") or err_obj.get("type") or "error")
        raise OpenAIHTTPAdapterError(
            msg[:512],
            code=CanaryRuntimeCode.HTTP_BAD_REQUEST.value,
        )

    output = data.get("output")
    if not isinstance(output, list):
        raise OpenAIHTTPAdapterError(
            "OpenAI response missing list output",
            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
        )
    text_parts: list[str] = []
    finish = "stop"
    for block in output:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "message":
            continue
        content = block.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"}:
                t = part.get("text")
                if isinstance(t, str):
                    text_parts.append(t)
    raw_joined = "\n".join(text_parts).strip() if text_parts else ""
    if not raw_joined:
        raise OpenAIHTTPAdapterError(
            "OpenAI response contained no output_text",
            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
        )
    try:
        parsed = json.loads(raw_joined)
    except json.JSONDecodeError as exc:
        raise OpenAIHTTPAdapterError(
            f"OpenAI output_text not valid JSON: {exc}",
            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
        ) from exc
    if not isinstance(parsed, dict):
        raise OpenAIHTTPAdapterError(
            "OpenAI JSON root must be an object",
            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
        )
    return parsed, raw_joined, finish


def _usage_tokens(data: dict[str, Any]) -> tuple[int, int]:
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        return 0, 0
    inp = usage.get("input_tokens")
    if inp is None:
        inp = usage.get("prompt_tokens")
    outp = usage.get("output_tokens")
    if outp is None:
        outp = usage.get("completion_tokens")
    try:
        return int(inp or 0), int(outp or 0)
    except (TypeError, ValueError):
        return 0, 0


def _map_status_to_exc(status_code: int) -> OpenAIHTTPAdapterError:
    if status_code in (401, 403):
        return OpenAIHTTPAdapterError(
            f"OpenAI HTTP {status_code}",
            code=CanaryRuntimeCode.HTTP_AUTH.value,
            status_code=status_code,
        )
    if status_code == 429:
        return OpenAIHTTPAdapterError(
            "OpenAI HTTP 429 rate limit",
            code=CanaryRuntimeCode.HTTP_RATE_LIMIT.value,
            status_code=status_code,
        )
    if status_code == 400:
        return OpenAIHTTPAdapterError(
            "OpenAI HTTP 400",
            code=CanaryRuntimeCode.HTTP_BAD_REQUEST.value,
            status_code=status_code,
        )
    if 500 <= status_code <= 599:
        return OpenAIHTTPAdapterError(
            f"OpenAI HTTP {status_code}",
            code=CanaryRuntimeCode.HTTP_SERVER.value,
            status_code=status_code,
        )
    return OpenAIHTTPAdapterError(
        f"OpenAI HTTP {status_code}",
        code=CanaryRuntimeCode.HTTP_BAD_REQUEST.value,
        status_code=status_code,
    )


class OpenAIStructuredProviderShell(AIProvider):
    """Bounded ``POST /v1/responses``; HTTP only when :func:`check_openai_responses_http_gates_or_raise` passes."""

    name = "openai"

    def __init__(self) -> None:
        check_openai_structured_adapter_construct_gates_or_raise()

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        check_openai_responses_http_gates_or_raise()
        json_schema = _json_schema_for_request(request)
        payload = _build_request_payload(request, json_schema=json_schema)
        cap_cfg = load_ai_canary_gate_config_from_env()
        per_call_timeout = min(int(request.timeout_seconds), int(cap_cfg.timeout_seconds))
        max_retries = int(os.environ.get("AI_CANARY_HTTP_MAX_RETRIES", "0") or "0")
        max_retries = max(0, max_retries)

        base = _responses_base_url()
        url = f"{base}/v1/responses"
        headers = {
            "Authorization": f"Bearer {(os.environ.get('OPENAI_API_KEY') or '').strip()}",
            "Content-Type": "application/json",
        }
        log.info(
            "openai_responses_request model=%s stage=%s trace_id=%s url=%s",
            request.model,
            request.stage_name,
            request.trace_id,
            url,
        )
        t0 = time.perf_counter()
        retry_count = 0
        last_exc: OpenAIHTTPAdapterError | None = None

        with httpx.Client(timeout=httpx.Timeout(per_call_timeout)) as client:
            for attempt in range(max_retries + 1):
                try:
                    resp = client.post(url, headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    raise OpenAIHTTPAdapterError(
                        str(exc),
                        code=CanaryRuntimeCode.HTTP_TIMEOUT.value,
                    ) from exc
                except httpx.RequestError as exc:
                    raise OpenAIHTTPAdapterError(
                        str(exc),
                        code=CanaryRuntimeCode.HTTP_NETWORK.value,
                    ) from exc

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except json.JSONDecodeError as exc:
                        raise OpenAIHTTPAdapterError(
                            "OpenAI response body not JSON",
                            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
                        ) from exc
                    if not isinstance(data, dict):
                        raise OpenAIHTTPAdapterError(
                            "OpenAI response JSON not an object",
                            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
                        )
                    parsed, raw_text, finish = _parse_success_json(data)
                    in_tok, out_tok = _usage_tokens(data)
                    rid = str(data.get("id") or "")
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    meta: dict[str, Any] = {
                        "object": data.get("object"),
                        "model": data.get("model"),
                    }
                    if isinstance(data.get("usage"), dict):
                        meta["usage"] = data["usage"]
                    return AICompletionResponse(
                        parsed_json=parsed,
                        raw_text=raw_text,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_estimate=0.0,
                        latency_ms=max(latency_ms, 0),
                        provider_request_id=rid,
                        finish_reason=finish,
                        provider_name=self.name,
                        retry_count=retry_count,
                        raw_response_meta=meta,
                    )

                last_exc = _map_status_to_exc(resp.status_code)
                if attempt >= max_retries:
                    break
                if resp.status_code != 429 and not (500 <= resp.status_code <= 599):
                    break
                retry_count += 1

        if last_exc:
            log.warning(
                "openai_responses_http_error code=%s status=%s",
                last_exc.code,
                last_exc.status_code,
            )
            raise last_exc
        raise OpenAIHTTPAdapterError(
            "OpenAI request failed with unknown state",
            code=CanaryRuntimeCode.HTTP_MALFORMED.value,
        )
