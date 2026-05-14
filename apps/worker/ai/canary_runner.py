"""Tiny staging-only OpenAI canary runner — **synthetic fixture input only**.

Requires ``FF_OPENAI_CANARY_RUNNER_ENABLED=true`` **plus** full structured OpenAI canary
gates (see ``docs/phase7-openai-canary.md``). Uses ``p7-canary-v1`` JSON Schema for live
HTTP. Independent of ``FF_WORKER_AI_ENRICHMENT_ENABLED``.

Manual preflight (no HTTP, Gate A): ``python -m ai.canary_runner --fixture tiny_transcript --dry-run``
from ``apps/worker`` with ``PYTHONPATH=../api:.`` (see docs).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from sqlmodel import Session

from ai.canary_error_codes import CanaryRuntimeCode
from ai.openai_adapter import OpenAIHTTPAdapterError
from ai.modules.output_validator import OutputValidator, ValidationStatus
from ai.modules.transcript_intelligence import chunks_from_plain_text
from ai.openai_canary_gates import check_openai_responses_http_gates_or_raise
from ai.provider import AIProvider
from ai.provider_mode import ProviderDisabledError
from ai.registry import get_structured_ai_provider
from ai.schemas.output_contracts import (
    FACTSHEET_SCHEMA_NAME,
    FACTSHEET_SCHEMA_VERSION,
    P7_CANARY_LIVE_SCHEMA_NAME,
    P7_CANARY_LIVE_SCHEMA_VERSION,
)
from ai.transcript_context import TranscriptChunkInput
from ai.types import AICompletionRequest
from app.models import AIRun, AIStageLog, Job, utcnow
from app.services.ai_internal_policy import load_ai_canary_gate_config_from_env

log = logging.getLogger("feedfoundry.worker.ai.canary_runner")

ENV_OPENAI_CANARY_RUNNER = "FF_OPENAI_CANARY_RUNNER_ENABLED"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "canary_synthetic_transcript.txt"
FIXTURE_TINY_TRANSCRIPT = "tiny_transcript"
CANARY_STAGE = "openai_canary_synthetic"


def _truthy_env(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def openai_canary_runner_enabled() -> bool:
    return _truthy_env(os.environ.get(ENV_OPENAI_CANARY_RUNNER))


def fixture_path_for_id(fixture_id: str) -> Path:
    if fixture_id == FIXTURE_TINY_TRANSCRIPT:
        return FIXTURE_PATH
    raise ValueError(f"Unknown fixture_id={fixture_id!r}; supported: {FIXTURE_TINY_TRANSCRIPT!r}")


def redacted_openai_canary_preflight_summary(*, fixture_id: str) -> dict[str, Any]:
    """Ops-safe snapshot for ``--dry-run`` (no secrets, no bodies)."""

    cfg = load_ai_canary_gate_config_from_env()
    key = os.environ.get("OPENAI_API_KEY") or ""
    base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
    retries_raw = os.environ.get("AI_CANARY_HTTP_MAX_RETRIES", "0") or "0"
    try:
        retries = int(retries_raw)
    except ValueError:
        retries = -1
    return {
        "fixture_id": fixture_id,
        "fixture_file": fixture_path_for_id(fixture_id).name,
        "AI_STRUCTURED_PROVIDER_MODE": os.environ.get("AI_STRUCTURED_PROVIDER_MODE"),
        "AI_PROVIDER": (os.environ.get("AI_PROVIDER") or "").strip() or None,
        "AI_ENABLE_MOCK_PROVIDER": os.environ.get("AI_ENABLE_MOCK_PROVIDER"),
        "AI_CANARY_ENABLED": cfg.canary_enabled,
        "AI_ENABLE_REAL_PROVIDER": cfg.real_provider_enabled,
        "AI_CANARY_MAX_CALLS": cfg.max_calls,
        "AI_CANARY_MAX_COST": cfg.max_cost,
        "AI_CANARY_TIMEOUT_SECONDS": cfg.timeout_seconds,
        "AI_CANARY_HTTP_MAX_RETRIES": retries,
        "FF_OPENAI_CANARY_RUNNER_ENABLED": openai_canary_runner_enabled(),
        "OPENAI_API_KEY": "present" if bool(key.strip()) else "absent",
        "OPENAI_BASE_URL_set": bool(base),
        "AI_MODEL": (os.environ.get("AI_MODEL") or "").strip() or None,
    }


def _load_fixture_plain_text(fixture_path: Path) -> str:
    return fixture_path.read_text(encoding="utf-8").strip()


def _input_bundle_for_chunk(chunk: TranscriptChunkInput, *, episode_title: str | None) -> dict[str, Any]:
    return {
        "chunk_index": chunk.chunk_index,
        "transcript_text": chunk.text,
        "segment_id": chunk.segment_id,
        "start_ms": chunk.start_ms,
        "end_ms": chunk.end_ms,
        "episode_title": episode_title,
    }


def _append_stage_log(
    session: Session,
    *,
    ai_run_id: str,
    job_id: str,
    stage_name: str,
    status: str,
    provider_name: str | None,
    model_name: str | None,
    started_at,
    finished_at,
    input_tokens: int,
    output_tokens: int,
    cost_estimate_internal: float | None,
    validation_status: str | None,
    error_code: str | None,
    error_message: str | None,
    provider_request_id: str | None,
    extra_json: dict[str, Any] | None = None,
) -> None:
    row = AIStageLog(
        ai_run_id=ai_run_id,
        job_id=job_id,
        stage_name=stage_name,
        status=status,
        provider_name=provider_name,
        model_name=model_name,
        started_at=started_at,
        finished_at=finished_at,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_estimate_internal=cost_estimate_internal,
        validation_status=validation_status,
        error_code=error_code,
        error_message=error_message,
        provider_request_id=provider_request_id,
        extra_json=extra_json,
    )
    session.add(row)
    session.commit()


def run_openai_canary_fixture_pipeline(
    session: Session,
    job: Job,
    prov: AIProvider,
    *,
    fixture_path: Path | None = None,
) -> None:
    """One structured call on **fixture** text only; persists AIRun / AIStageLog.

    Uses ``p7-canary-v1`` JSON Schema for OpenAI ``strict`` mode; output is validated
    against the production ``FactsheetPayload`` contract.
    """

    path = fixture_path or FIXTURE_PATH
    text = _load_fixture_plain_text(path)
    chunks = chunks_from_plain_text(text, max_chars=1200, overlap=80)
    if not chunks:
        log.warning("openai_canary_runner_empty_fixture job_id=%s", job.id)
        return

    chunk0 = chunks[0]
    bundle = _input_bundle_for_chunk(chunk0, episode_title="openai-canary-fixture")
    validator = OutputValidator()
    now = utcnow()
    airun = AIRun(
        job_id=job.id,
        organisation_id=job.organisation_id,
        status="running",
        captain_plan_version="p7-openai-canary-runner-1",
        created_at=now,
        updated_at=now,
    )
    session.add(airun)
    session.commit()
    session.refresh(airun)
    run_id = airun.id
    model = (os.environ.get("AI_MODEL") or "gpt-4.1-mini").strip()

    def _finish(final: str, *, error_code: str | None = None, error_message: str | None = None) -> None:
        r = session.get(AIRun, run_id)
        if not r:
            return
        r.status = final
        r.error_code = error_code
        r.error_message = (error_message or "")[:1024] if error_message else None
        r.updated_at = utcnow()
        session.add(r)
        session.commit()

    t0 = utcnow()
    req = AICompletionRequest(
        stage_name=CANARY_STAGE,
        schema_name=P7_CANARY_LIVE_SCHEMA_NAME,
        schema_version=P7_CANARY_LIVE_SCHEMA_VERSION,
        prompt_version="p7-openai-canary-runner-1",
        model=model,
        input_bundle=bundle,
        max_tokens=256,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id=f"{job.id}:openai-canary:fixture",
    )
    extra_fixture = {"fixture": path.name}
    try:
        resp = prov.complete(req)
        t1 = utcnow()
        vres = validator.validate_payload(
            schema_name=FACTSHEET_SCHEMA_NAME,
            schema_version=FACTSHEET_SCHEMA_VERSION,
            payload=resp.parsed_json,
        )
        if vres.status != ValidationStatus.ACCEPTED:
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=CANARY_STAGE,
                status="failed",
                provider_name=prov.name,
                model_name=model,
                started_at=t0,
                finished_at=t1,
                input_tokens=int(resp.input_tokens or 0),
                output_tokens=int(resp.output_tokens or 0),
                cost_estimate_internal=float(resp.cost_estimate or 0.0) or None,
                validation_status=vres.status.value,
                error_code="openai_canary_output_validation",
                error_message=str(vres.errors)[:2048],
                provider_request_id=resp.provider_request_id,
                extra_json=extra_fixture,
            )
            _finish("failed", error_code="openai_canary_output_validation", error_message=str(vres.errors))
            return
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=CANARY_STAGE,
            status="completed",
            provider_name=prov.name,
            model_name=model,
            started_at=t0,
            finished_at=t1,
            input_tokens=int(resp.input_tokens or 0),
            output_tokens=int(resp.output_tokens or 0),
            cost_estimate_internal=float(resp.cost_estimate or 0.0) or None,
            validation_status=ValidationStatus.ACCEPTED.value,
            error_code=None,
            error_message=None,
            provider_request_id=resp.provider_request_id,
            extra_json=extra_fixture,
        )
        _finish("completed")
    except OpenAIHTTPAdapterError as exc:
        t1 = utcnow()
        code = exc.code
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=CANARY_STAGE,
            status="failed",
            provider_name=prov.name,
            model_name=model,
            started_at=t0,
            finished_at=t1,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=code,
            error_message=str(exc)[:2048],
            provider_request_id=None,
            extra_json={**extra_fixture, "adapter": "http"},
        )
        _finish("failed", error_code=code, error_message=str(exc))
    except RuntimeError as exc:
        t1 = utcnow()
        code = CanaryRuntimeCode.ADAPTER_HTTP_NOT_WIRED.value
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=CANARY_STAGE,
            status="failed",
            provider_name=prov.name,
            model_name=model,
            started_at=t0,
            finished_at=t1,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=code,
            error_message=str(exc)[:2048],
            provider_request_id=None,
            extra_json={**extra_fixture, "adapter": "shell"},
        )
        _finish("failed", error_code=code, error_message=str(exc))


def maybe_run_openai_canary_job_runner(session: Session, job: Job) -> None:
    """If runner + OpenAI canary gates pass, run one structured call on **fixture** text only."""

    if not openai_canary_runner_enabled():
        return
    try:
        prov = get_structured_ai_provider()
    except ProviderDisabledError as exc:
        log.info("openai_canary_runner_skipped job_id=%s reason=%s", job.id, exc)
        return
    if prov.name != "openai":
        return

    run_openai_canary_fixture_pipeline(session, job, prov)


def manual_run_openai_canary_preflight(
    *,
    dry_run: bool,
    fixture_id: str,
    session: Session | None,
    job: Job | None,
) -> dict[str, Any] | None:
    """Fail closed via :func:`check_openai_responses_http_gates_or_raise`.

    When ``dry_run`` is True, returns a redacted summary dict and performs no HTTP or DB writes.
    When ``dry_run`` is False, requires ``session`` and ``job`` and runs
    :func:`run_openai_canary_fixture_pipeline` (HTTP unless transport is mocked).
    """

    check_openai_responses_http_gates_or_raise()
    prov = get_structured_ai_provider()
    if prov.name != "openai":
        raise ProviderDisabledError("structured provider is not openai after canary gates")
    fixture_path = fixture_path_for_id(fixture_id)
    if dry_run:
        summary = redacted_openai_canary_preflight_summary(fixture_id=fixture_id)
        summary["dry_run"] = True
        summary["would_call_http"] = True
        summary["hint"] = "Gate A: use --dry-run for preflight; live HTTP requires explicit captain approval phrase."
        return summary

    if session is None or job is None:
        raise ValueError("session and job are required when dry_run is False")
    run_openai_canary_fixture_pipeline(session, job, prov, fixture_path=fixture_path)
    return None


def cli_main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("AI_LOG_LEVEL", "INFO"))
    p = argparse.ArgumentParser(description="OpenAI structured canary (synthetic fixture only).")
    p.add_argument(
        "--fixture",
        default=FIXTURE_TINY_TRANSCRIPT,
        choices=[FIXTURE_TINY_TRANSCRIPT],
        help="Synthetic fixture id (default: tiny_transcript).",
    )
    p.add_argument("--dry-run", action="store_true", help="Preflight: gates + redacted summary; no HTTP or DB.")
    p.add_argument("--preflight", action="store_true", help="Alias for --dry-run.")
    p.add_argument(
        "--job-id",
        default=None,
        help="Job UUID for AIRun attachment (required when not using --dry-run / --preflight).",
    )
    args = p.parse_args(argv)
    dry = bool(args.dry_run or args.preflight)

    try:
        if dry:
            summary = manual_run_openai_canary_preflight(
                dry_run=True,
                fixture_id=args.fixture,
                session=None,
                job=None,
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0

        if not args.job_id:
            print("error: --job-id is required without --dry-run", file=sys.stderr)
            return 2
        db_url = (os.environ.get("DATABASE_URL") or "").strip()
        if not db_url:
            print("error: DATABASE_URL is required for non-dry-run", file=sys.stderr)
            return 2

        from sqlalchemy import create_engine

        engine = create_engine(db_url, pool_pre_ping=True)
        with Session(engine) as session:
            row = session.get(Job, args.job_id)
            if row is None:
                print(f"error: job not found: {args.job_id}", file=sys.stderr)
                return 2
            manual_run_openai_canary_preflight(
                dry_run=False,
                fixture_id=args.fixture,
                session=session,
                job=row,
            )
        return 0
    except ProviderDisabledError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
