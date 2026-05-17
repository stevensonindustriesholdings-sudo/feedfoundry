"""HTTP client for ceo-hermes-worker (Hermes-first kernel; OpenAI/OpenRouter only on worker)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

log = logging.getLogger("feedfoundry.worker.hermes_kernel")


def hermes_worker_base_url() -> str:
    return (
        (os.environ.get("SI_HERMES_WORKER_URL") or os.environ.get("HERMES_WORKER_URL") or "").strip().rstrip("/")
    )


def post_kernel_run(
    *,
    kernel_id: str,
    product: str,
    task: str,
    payload: Any = None,
    ledger_run_id: str | None = None,
    timeout_seconds: float = 120.0,
) -> tuple[bool, int, dict[str, Any]]:
    """POST /v1/kernel/run. Returns (ok, http_status, body_or_error_dict)."""
    base = hermes_worker_base_url()
    if not base:
        return False, 0, {"error": "SI_HERMES_WORKER_URL_missing", "detail": "Set SI_HERMES_WORKER_URL or HERMES_WORKER_URL"}

    body: dict[str, Any] = {
        "kernel_id": kernel_id,
        "product": product,
        "task": task,
        "payload": payload,
        "ledger_run_id": ledger_run_id or str(uuid.uuid4()),
        "governor": {
            "max_output_tokens": 256,
            "max_output_chars": 4000,
            "allow_openai_fallback": True,
            "allow_openrouter_fallback": False,
        },
        "preferred_provider": "openai",
        "hermes_first_route": "feedfoundry_worker_probe_v1",
    }

    try:
        import httpx
    except ImportError:
        return False, 0, {"error": "httpx_missing"}

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            r = client.post(f"{base}/v1/kernel/run", headers={"Content-Type": "application/json"}, json=body)
    except Exception as exc:
        return False, 0, {"error": type(exc).__name__}

    try:
        data = r.json()
    except json.JSONDecodeError:
        data = {"error": "invalid_json", "text": (r.text or "")[:800]}

    return r.status_code < 400, r.status_code, data if isinstance(data, dict) else {"raw": data}


def log_kernel_probe(job_id: str) -> None:
    """One bounded kernel call per job when worker URL is set; logs llm_path (no secrets)."""
    if not hermes_worker_base_url():
        return
    ok, status, body = post_kernel_run(
        kernel_id="feedfoundry_worker_router_probe",
        product="feedfoundry",
        task=f"worker_ai_router_probe_echo job_id={job_id}",
        payload={"job_id": job_id, "source": "feedfoundry_worker"},
        timeout_seconds=90.0,
    )
    llm_path = body.get("llm_path") if isinstance(body, dict) else None
    if ok:
        log.info(
            "hermes_kernel_probe job_id=%s http_status=%s llm_path=%s fallback_used=%s",
            job_id,
            status,
            llm_path,
            body.get("fallback_used"),
        )
    else:
        log.warning(
            "hermes_kernel_probe_fail job_id=%s http_status=%s llm_path=%s err=%s",
            job_id,
            status,
            llm_path,
            body.get("error") if isinstance(body, dict) else "unknown",
        )
