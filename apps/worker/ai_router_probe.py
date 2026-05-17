"""Env-gated AI router probe from the worker (mock logs by default)."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("feedfoundry.worker.ai_probe")


def _truthy(name: str) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def run_worker_ai_router_probe(job_id: str) -> None:
    from app.services.ai_router import AIResponseLog, build_request_for_module, load_ai_routing
    from app.settings import get_settings

    settings = get_settings()
    path = settings.ai_routing_config_path
    if not path or not Path(path).is_file():
        log.info("ai_router_probe_skip job_id=%s reason=no_routing_file", job_id)
        return
    routing = load_ai_routing(path)
    resolver = {
        "OPENROUTER_ROUTER_PROBE_MODEL": os.environ.get("OPENROUTER_ROUTER_PROBE_MODEL", "openai/gpt-4o-mini"),
        "OPENAI_CHEAP_TEXT_MODEL": os.environ.get("OPENAI_CHEAP_TEXT_MODEL", "gpt-4o-mini"),
    }
    try:
        spec = build_request_for_module(
            routing=routing,
            module_name="worker_router_probe",
            job_id=job_id,
            model_resolver=resolver,
        )
    except Exception:
        log.warning("ai_router_probe_skip job_id=%s reason=spec_build", job_id, exc_info=False)
        return

    if not _truthy("FF_AI_LIVE_CALLS_ENABLED"):
        log.info(
            "ai_router_probe_mock job_id=%s module=%s provider=%s model=%s",
            job_id,
            spec.module_name,
            spec.provider,
            spec.model,
        )
        return

    or_key = (os.environ.get("OPENROUTER_API_KEY") or getattr(settings, "openrouter_api_key", "") or "").strip()
    oa_key = (os.environ.get("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "") or "").strip()
    if or_key.lower() in ("", "replace_me") and oa_key.lower() in ("", "replace_me"):
        log.info("ai_router_probe_skip_live job_id=%s reason=no_provider_keys", job_id)
        return

    try:
        import httpx
    except ImportError:
        log.warning("ai_router_probe_skip job_id=%s reason=no_httpx", job_id)
        return

    messages = [{"role": "user", "content": 'Reply with exactly one word: "ok".'}]
    t0 = time.monotonic()
    ok = False
    status_code = 0
    out_tokens: int | None = None
    provider_used = "none"
    model_used = spec.model

    if or_key and or_key.lower() != "replace_me":
        provider_used = "openrouter"
        model_used = spec.model
        try:
            with httpx.Client(timeout=float(spec.timeout_seconds)) as client:
                r = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {or_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_used,
                        "messages": messages,
                        "max_tokens": min(int(spec.max_output_tokens), 32),
                        "temperature": float(spec.temperature),
                    },
                )
            status_code = r.status_code
            ok = r.status_code < 400
            if ok:
                try:
                    body = r.json()
                    usage = body.get("usage") or {}
                    ot = usage.get("completion_tokens")
                    out_tokens = int(ot) if ot is not None else None
                except Exception:
                    out_tokens = None
        except Exception as exc:
            log.warning("ai_router_probe_openrouter_err job_id=%s err=%s", job_id, type(exc).__name__)
    elif oa_key and oa_key.lower() != "replace_me":
        provider_used = "openai"
        model_used = resolver.get("OPENAI_CHEAP_TEXT_MODEL", "gpt-4o-mini")
        try:
            with httpx.Client(timeout=float(spec.timeout_seconds)) as client:
                r = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {oa_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_used,
                        "messages": messages,
                        "max_tokens": min(int(spec.max_output_tokens), 32),
                        "temperature": float(spec.temperature),
                    },
                )
            status_code = r.status_code
            ok = r.status_code < 400
            if ok:
                try:
                    body = r.json()
                    usage = body.get("usage") or {}
                    ot = usage.get("completion_tokens")
                    out_tokens = int(ot) if ot is not None else None
                except Exception:
                    out_tokens = None
        except Exception as exc:
            log.warning("ai_router_probe_openai_err job_id=%s err=%s", job_id, type(exc).__name__)

    latency_ms = int((time.monotonic() - t0) * 1000)
    al = AIResponseLog(
        provider=provider_used,
        model=model_used,
        module_name=spec.module_name,
        job_id=job_id,
        input_tokens_estimated=24,
        output_tokens_reported_or_estimated=out_tokens,
        latency_ms=latency_ms,
        success=ok,
        retry_count=0,
        cost_estimate=0.0 if ok else None,
    )
    log.info(
        "ai_router_probe_live job_id=%s http_status=%s log=%s",
        job_id,
        status_code,
        al.model_dump(),
    )
