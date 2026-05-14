"""Tiny staging-only OpenAI canary runner — **synthetic fixture input only**.

Requires ``FF_OPENAI_CANARY_RUNNER_ENABLED=true`` **plus** full structured OpenAI canary
gates (see ``docs/phase7-openai-canary.md``). Independent of ``FF_WORKER_AI_ENRICHMENT_ENABLED``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from sqlmodel import Session

from ai.canary_error_codes import CanaryRuntimeCode
from ai.modules.output_validator import OutputValidator, ValidationStatus
from ai.modules.transcript_intelligence import chunks_from_plain_text
from ai.provider_mode import ProviderDisabledError
from ai.registry import get_structured_ai_provider
from ai.schemas.output_contracts import FACTSHEET_SCHEMA_NAME, FACTSHEET_SCHEMA_VERSION
from ai.transcript_context import TranscriptChunkInput
from ai.types import AICompletionRequest
from app.models import AIRun, AIStageLog, Job, utcnow

log = logging.getLogger("feedfoundry.worker.ai.canary_runner")

ENV_OPENAI_CANARY_RUNNER = "FF_OPENAI_CANARY_RUNNER_ENABLED"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "canary_synthetic_transcript.txt"
CANARY_STAGE = "openai_canary_synthetic"


def _truthy_env(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def openai_canary_runner_enabled() -> bool:
    return _truthy_env(os.environ.get(ENV_OPENAI_CANARY_RUNNER))


def _load_fixture_plain_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8").strip()


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


def maybe_run_openai_canary_job_runner(session: Session, job: Job) -> None:
    """If runner + OpenAI canary gates pass, run one factsheet call on **fixture** text only."""

    if not openai_canary_runner_enabled():
        return
    try:
        prov = get_structured_ai_provider()
    except ProviderDisabledError as exc:
        log.info("openai_canary_runner_skipped job_id=%s reason=%s", job.id, exc)
        return
    if prov.name != "openai":
        return

    text = _load_fixture_plain_text()
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
        schema_name=FACTSHEET_SCHEMA_NAME,
        schema_version=FACTSHEET_SCHEMA_VERSION,
        prompt_version="p7-openai-canary-runner-1",
        model=model,
        input_bundle=bundle,
        max_tokens=256,
        temperature=0.0,
        timeout_seconds=30,
        cost_cap=0.0,
        trace_id=f"{job.id}:openai-canary:fixture",
    )
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
                extra_json={"fixture": FIXTURE_PATH.name},
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
            extra_json={"fixture": FIXTURE_PATH.name},
        )
        _finish("completed")
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
            extra_json={"fixture": FIXTURE_PATH.name, "adapter": "shell"},
        )
        _finish("failed", error_code=code, error_message=str(exc))
