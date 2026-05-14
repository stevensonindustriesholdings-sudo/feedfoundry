"""Optional mock-only AI enrichment in the worker job path (Phase 7C).

Gated by ``FF_WORKER_AI_ENRICHMENT_ENABLED`` (default **off**). Uses
:class:`ai.mock_provider.MockAIProvider` only — no real provider SDKs or HTTP.
Persists :class:`app.models.AIRun` / :class:`app.models.AIStageLog` via the same
SQLModel ``Session`` as the job; does not touch credit ledger or processing-minute
settlement.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlmodel import Session

from ai.mock_provider import MockAIProvider
from ai.modules.output_validator import ValidationStatus
from ai.modules.product_signal import STAGE_NAME as PRODUCT_STAGE
from ai.modules.product_signal import ProductSignalValidationError, run_product_signal
from ai.modules.transcript_intelligence import STAGE_NAME as TRANSCRIPT_STAGE
from ai.modules.transcript_intelligence import (
    TranscriptIntelligenceValidationError,
    chunks_from_plain_text,
    run_transcript_intelligence,
)
from ai.modules.visual_analysis import STAGE_NAME as VISUAL_STAGE
from ai.modules.visual_analysis import VisualAnalysisValidationError, run_visual_analysis
from ai.product_context import ProductGridContext, ProductSignalContext
from ai.provider import AIProvider
from ai.transcript_context import TranscriptChunkInput
from ai.types import AICompletionRequest, AICompletionResponse
from ai.visual_context import KeyframeRef, OCRSnippetRef, ProductImageRef, VisualAnalysisContext
from app.models import AIRun, AIStageLog, Job, JobStatus, utcnow

log = logging.getLogger("feedfoundry.worker.ai.pipeline")

# Default **off** — production behaviour unchanged unless explicitly enabled.
ENV_AI_ENRICHMENT = "FF_WORKER_AI_ENRICHMENT_ENABLED"


def _truthy_env(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def worker_ai_enrichment_enabled() -> bool:
    return _truthy_env(os.environ.get(ENV_AI_ENRICHMENT))


class _AccountingMockProvider(AIProvider):
    """Wraps :class:`MockAIProvider` to sum token / cost fields for stage logs."""

    name = "mock"

    def __init__(self) -> None:
        self._inner = MockAIProvider()
        self.input_tokens_total = 0
        self.output_tokens_total = 0
        self.cost_estimate_total = 0.0
        self.last_request_id: str | None = None

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        resp = self._inner.complete(request)
        self.input_tokens_total += int(resp.input_tokens or 0)
        self.output_tokens_total += int(resp.output_tokens or 0)
        self.cost_estimate_total += float(resp.cost_estimate or 0.0)
        self.last_request_id = resp.provider_request_id
        return resp


def _job_is_cancelled(session: Session, job_id: str) -> bool:
    row = session.get(Job, job_id)
    return bool(row and row.status == JobStatus.CANCELLED)


def _transcript_plain_text(transcript_payload: dict[str, Any] | None) -> str | None:
    if not transcript_payload:
        return None
    parts: list[str] = []
    for seg in transcript_payload.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        t = (seg.get("text") or "").strip()
        if t:
            parts.append(t)
    if not parts:
        return None
    return "\n".join(parts)


def _parse_keyframes(mi: dict[str, Any]) -> tuple[KeyframeRef, ...]:
    raw = mi.get("keyframes")
    out: list[KeyframeRef] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict) or row.get("frame_id") is None:
                continue
            try:
                t_ms = int(row.get("t_ms", 0))
            except (TypeError, ValueError):
                t_ms = 0
            out.append(KeyframeRef(frame_id=str(row["frame_id"]), t_ms=t_ms))
    return tuple(out)


def _parse_ocr_snippets(mi: dict[str, Any]) -> tuple[OCRSnippetRef, ...]:
    raw = mi.get("ocr_snippets")
    out: list[OCRSnippetRef] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict) or row.get("ocr_source_id") is None:
                continue
            try:
                t_ms = int(row.get("t_ms", 0))
            except (TypeError, ValueError):
                t_ms = 0
            text = str(row.get("text") or "")
            out.append(OCRSnippetRef(ocr_source_id=str(row["ocr_source_id"]), t_ms=t_ms, text=text))
    return tuple(out)


def _parse_product_images_for_visual(mi: dict[str, Any]) -> tuple[ProductImageRef, ...]:
    raw = mi.get("product_images")
    out: list[ProductImageRef] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict) or not row.get("product_image_id"):
                continue
            t_raw = row.get("t_ms")
            try:
                t_ms = int(t_raw) if t_raw is not None else None
            except (TypeError, ValueError):
                t_ms = None
            out.append(
                ProductImageRef(
                    product_image_id=str(row["product_image_id"]),
                    t_ms=t_ms,
                    grid_cell_index=row.get("grid_cell_index"),
                )
            )
    return tuple(out)


def _visual_context_from_inspection(
    mi: dict[str, Any],
    *,
    episode_id: str,
) -> VisualAnalysisContext | None:
    """Return a context only when at least one visual input row is present (no chunk_plan synthesis)."""
    kfs = _parse_keyframes(mi)
    ocr = _parse_ocr_snippets(mi)
    pimgs = _parse_product_images_for_visual(mi)
    if not kfs and not ocr and not pimgs:
        return None
    return VisualAnalysisContext(episode_id=episode_id, keyframes=kfs, ocr_snippets=ocr, product_images=pimgs)


def _product_images_for_signal(mi: dict[str, Any]) -> tuple[ProductImageRef, ...]:
    return _parse_product_images_for_visual(mi)


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


def maybe_run_mock_ai_job_enrichment(
    session: Session,
    job: Job,
    *,
    transcript_payload: dict[str, Any] | None,
    media_inspection_payload: dict[str, Any] | None,
) -> None:
    """If ``FF_WORKER_AI_ENRICHMENT_ENABLED`` is on, run mock stages and persist logs (best-effort)."""
    if not worker_ai_enrichment_enabled():
        return

    text = _transcript_plain_text(transcript_payload)
    vctx = (
        _visual_context_from_inspection(media_inspection_payload, episode_id=job.id)
        if media_inspection_payload
        else None
    )
    pimgs = _product_images_for_signal(media_inspection_payload) if media_inspection_payload else ()

    if not text and vctx is None and not pimgs:
        return

    prov = _AccountingMockProvider()
    now = utcnow()
    airun = AIRun(
        job_id=job.id,
        organisation_id=job.organisation_id,
        status="running",
        captain_plan_version="p7-worker-mock-enrichment-1",
        created_at=now,
        updated_at=now,
    )
    session.add(airun)
    session.commit()
    session.refresh(airun)
    run_id = airun.id

    def _finish_run(final: str, *, error_code: str | None = None, error_message: str | None = None) -> None:
        r = session.get(AIRun, run_id)
        if not r:
            return
        r.status = final
        r.error_code = error_code
        r.error_message = error_message
        r.updated_at = utcnow()
        session.add(r)
        session.commit()

    if _job_is_cancelled(session, job.id):
        _finish_run("cancelled", error_code="cancelled", error_message="Job already cancelled before enrichment.")
        return

    # --- transcript_intelligence ---
    if not text:
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=TRANSCRIPT_STAGE,
            status="skipped",
            provider_name=None,
            model_name=None,
            started_at=None,
            finished_at=None,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=None,
            error_message="no_transcript_text",
            provider_request_id=None,
            extra_json={"reason": "missing_segments"},
        )
    else:
        if _job_is_cancelled(session, job.id):
            _finish_run("cancelled", error_code="cancelled", error_message="Cancelled before transcript_intelligence.")
            return
        t0 = utcnow()
        chunks: list[TranscriptChunkInput] = chunks_from_plain_text(text, max_chars=1200, overlap=80)
        try:
            run_transcript_intelligence(chunks, job_id=job.id, provider=prov, episode_title=None)
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=TRANSCRIPT_STAGE,
                status="completed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov.input_tokens_total,
                output_tokens=prov.output_tokens_total,
                cost_estimate_internal=prov.cost_estimate_total or None,
                validation_status=ValidationStatus.ACCEPTED.value,
                error_code=None,
                error_message=None,
                provider_request_id=prov.last_request_id,
                extra_json={"chunks": len(chunks)},
            )
        except TranscriptIntelligenceValidationError as exc:
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=TRANSCRIPT_STAGE,
                status="failed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov.input_tokens_total,
                output_tokens=prov.output_tokens_total,
                cost_estimate_internal=prov.cost_estimate_total or None,
                validation_status=ValidationStatus.REJECTED.value,
                error_code="transcript_intelligence_validation",
                error_message=str(exc)[:2048],
                provider_request_id=prov.last_request_id,
                extra_json=None,
            )
            log.warning("mock_ai_transcript_validation_failed job_id=%s err=%s", job.id, exc)

    if _job_is_cancelled(session, job.id):
        _finish_run("cancelled", error_code="cancelled", error_message="Cancelled after transcript_intelligence.")
        return

    # --- visual_analysis ---
    if not media_inspection_payload:
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=VISUAL_STAGE,
            status="skipped",
            provider_name=None,
            model_name=None,
            started_at=None,
            finished_at=None,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=None,
            error_message="no_media_inspection",
            provider_request_id=None,
            extra_json=None,
        )
    elif vctx is None:
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=VISUAL_STAGE,
            status="skipped",
            provider_name=None,
            model_name=None,
            started_at=None,
            finished_at=None,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=None,
            error_message="no_visual_inputs",
            provider_request_id=None,
            extra_json={"reason": "no_keyframes_ocr_or_product_images"},
        )
    else:
        if _job_is_cancelled(session, job.id):
            _finish_run("cancelled", error_code="cancelled", error_message="Cancelled before visual_analysis.")
            return
        t0 = utcnow()
        prov_v = _AccountingMockProvider()
        try:
            vres, _parsed = run_visual_analysis(vctx, job_id=job.id, provider=prov_v)
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=VISUAL_STAGE,
                status="completed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov_v.input_tokens_total,
                output_tokens=prov_v.output_tokens_total,
                cost_estimate_internal=prov_v.cost_estimate_total or None,
                validation_status=vres.status.value,
                error_code=None,
                error_message=None,
                provider_request_id=prov_v.last_request_id,
                extra_json={"keyframes": len(vctx.keyframes), "ocr": len(vctx.ocr_snippets)},
            )
        except VisualAnalysisValidationError as exc:
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=VISUAL_STAGE,
                status="failed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov_v.input_tokens_total,
                output_tokens=prov_v.output_tokens_total,
                cost_estimate_internal=prov_v.cost_estimate_total or None,
                validation_status=ValidationStatus.REJECTED.value,
                error_code="visual_analysis_validation",
                error_message=str(exc)[:2048],
                provider_request_id=prov_v.last_request_id,
                extra_json=None,
            )
            log.warning("mock_ai_visual_validation_failed job_id=%s err=%s", job.id, exc)

    if _job_is_cancelled(session, job.id):
        _finish_run("cancelled", error_code="cancelled", error_message="Cancelled after visual_analysis.")
        return

    # --- product_signal ---
    if not media_inspection_payload:
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=PRODUCT_STAGE,
            status="skipped",
            provider_name=None,
            model_name=None,
            started_at=None,
            finished_at=None,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=None,
            error_message="no_media_inspection",
            provider_request_id=None,
            extra_json=None,
        )
    elif not pimgs:
        _append_stage_log(
            session,
            ai_run_id=run_id,
            job_id=job.id,
            stage_name=PRODUCT_STAGE,
            status="skipped",
            provider_name=None,
            model_name=None,
            started_at=None,
            finished_at=None,
            input_tokens=0,
            output_tokens=0,
            cost_estimate_internal=None,
            validation_status=None,
            error_code=None,
            error_message="no_product_images",
            provider_request_id=None,
            extra_json=None,
        )
    else:
        if _job_is_cancelled(session, job.id):
            _finish_run("cancelled", error_code="cancelled", error_message="Cancelled before product_signal.")
            return
        t0 = utcnow()
        grid = ProductGridContext(listing_id=f"job-{job.id}", product_images=pimgs)
        ps_ctx = ProductSignalContext(job_id=job.id, grid=grid, content_anchor_ms=0)
        prov_p = _AccountingMockProvider()
        try:
            pres, _parsed = run_product_signal(ps_ctx, job_id=job.id, provider=prov_p)
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=PRODUCT_STAGE,
                status="completed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov_p.input_tokens_total,
                output_tokens=prov_p.output_tokens_total,
                cost_estimate_internal=prov_p.cost_estimate_total or None,
                validation_status=pres.status.value,
                error_code=None,
                error_message=None,
                provider_request_id=prov_p.last_request_id,
                extra_json={"product_images": len(pimgs)},
            )
        except ProductSignalValidationError as exc:
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=PRODUCT_STAGE,
                status="failed",
                provider_name="mock",
                model_name="mock",
                started_at=t0,
                finished_at=t1,
                input_tokens=prov_p.input_tokens_total,
                output_tokens=prov_p.output_tokens_total,
                cost_estimate_internal=prov_p.cost_estimate_total or None,
                validation_status=ValidationStatus.REJECTED.value,
                error_code="product_signal_validation",
                error_message=str(exc)[:2048],
                provider_request_id=prov_p.last_request_id,
                extra_json=None,
            )
            log.warning("mock_ai_product_validation_failed job_id=%s err=%s", job.id, exc)

    if _job_is_cancelled(session, job.id):
        _finish_run("cancelled", error_code="cancelled", error_message="Cancelled after product_signal.")
        return

    _finish_run("completed")
