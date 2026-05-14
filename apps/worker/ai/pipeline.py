"""Optional AI enrichment in the worker job path (Phase 7C).

Gated by ``FF_WORKER_AI_ENRICHMENT_ENABLED`` (default **off**). By default uses
:class:`ai.mock_provider.MockAIProvider` only (no HTTP).

When ``AI_STRUCTURED_PROVIDER_MODE=canary_openai`` and structured canary gates pass,
``FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE=true`` and/or ``FF_OPENAI_CANARY_RUNNER_ENABLED=true``
allows bounded ``POST …/v1/responses`` for transcript intelligence (see
``FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS``). Visual and product stages stay mock-only.

Persists :class:`app.models.AIRun` / :class:`app.models.AIStageLog`; does not touch
credit ledger or processing-minute settlement.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlmodel import Session

from ai.mock_provider import MockAIProvider
from ai.modules.output_validator import ValidationStatus
from ai.openai_adapter import OpenAIHTTPAdapterError
from ai.openai_canary_gates import (
    check_openai_responses_http_gates_or_raise,
    check_openai_structured_adapter_construct_gates_or_raise,
)
from ai.provider_mode import ProviderDisabledError, StructuredProviderMode, resolve_structured_provider_mode
from ai.registry import get_structured_ai_provider
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
ENV_ENRICHMENT_OPENAI_LIVE = "FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE"
ENV_ENRICHMENT_OPENAI_MAX_CALLS = "FF_WORKER_AI_ENRICHMENT_OPENAI_MAX_CALLS"


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


class _BudgetedOpenaiThenMockProvider(AIProvider):
    """Routes the first *budget* completions to OpenAI, then mock (token/call cap)."""

    name = "openai"

    def __init__(self, openai: AIProvider, mock: AIProvider, *, budget: int) -> None:
        self._openai = openai
        self._mock = mock
        self._remaining = max(0, int(budget))
        self.live_calls_used = 0

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if self._remaining > 0:
            self._remaining -= 1
            self.live_calls_used += 1
            return self._openai.complete(request)
        return self._mock.complete(request)


class _AccountingAIProvider(AIProvider):
    """Wraps any :class:`AIProvider` for AIRun stage log aggregates."""

    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner
        self.input_tokens_total = 0
        self.output_tokens_total = 0
        self.cost_estimate_total = 0.0
        self.last_request_id: str | None = None

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def budgeted_hybrid(self) -> _BudgetedOpenaiThenMockProvider | None:
        return self._inner if isinstance(self._inner, _BudgetedOpenaiThenMockProvider) else None

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        resp = self._inner.complete(request)
        self.input_tokens_total += int(resp.input_tokens or 0)
        self.output_tokens_total += int(resp.output_tokens or 0)
        self.cost_estimate_total += float(resp.cost_estimate or 0.0)
        self.last_request_id = resp.provider_request_id
        return resp


def _enrichment_openai_live_requested() -> bool:
    return _truthy_env(os.environ.get(ENV_ENRICHMENT_OPENAI_LIVE))


def _enrichment_openai_max_calls() -> int:
    raw = os.environ.get(ENV_ENRICHMENT_OPENAI_MAX_CALLS, "4") or "4"
    try:
        return max(0, int(raw))
    except ValueError:
        return 4


def _resolve_transcript_intelligence_provider() -> tuple[AIProvider, str, str, int]:
    """Return (provider, stage_log_provider_label, model_name, live_budget_or_zero).

    Live path requires ``canary_openai`` plus structured + HTTP gates (runner and/or
    ``FF_WORKER_AI_ENRICHMENT_OPENAI_LIVE``).
    """
    if not _enrichment_openai_live_requested():
        return _AccountingMockProvider(), "mock", "mock", 0

    if resolve_structured_provider_mode() != StructuredProviderMode.CANARY_OPENAI:
        log.info("worker_enrichment_openai_skipped structured_mode_not_canary_openai")
        return _AccountingMockProvider(), "mock", "mock", 0

    try:
        check_openai_structured_adapter_construct_gates_or_raise()
        check_openai_responses_http_gates_or_raise()
    except ProviderDisabledError as exc:
        log.info("worker_enrichment_openai_skipped gates=%s", type(exc).__name__)
        return _AccountingMockProvider(), "mock", "mock", 0

    budget = _enrichment_openai_max_calls()
    if budget <= 0:
        log.info("worker_enrichment_openai_skipped budget_zero")
        return _AccountingMockProvider(), "mock", "mock", 0

    openai = get_structured_ai_provider()
    hybrid = _BudgetedOpenaiThenMockProvider(openai, MockAIProvider(), budget=budget)
    model = (os.environ.get("AI_MODEL") or "").strip() or "gpt-4.1-mini"
    return _AccountingAIProvider(hybrid), "openai", model, budget


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

    ti_prov, ti_log_provider, ti_model, _ti_budget = _resolve_transcript_intelligence_provider()
    plan_ver = (
        "p7-worker-enrichment-openai-budget-1" if ti_log_provider == "openai" else "p7-worker-mock-enrichment-1"
    )
    now = utcnow()
    airun = AIRun(
        job_id=job.id,
        organisation_id=job.organisation_id,
        status="running",
        captain_plan_version=plan_ver,
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
            ti_artifacts = run_transcript_intelligence(
                chunks, job_id=job.id, provider=ti_prov, episode_title=None, model=ti_model
            )
            t1 = utcnow()
            bh = ti_prov.budgeted_hybrid if isinstance(ti_prov, _AccountingAIProvider) else None
            live_used = bh.live_calls_used if bh else 0
            artifact_digest: list[dict[str, Any]] = []
            for a in ti_artifacts:
                mdl = a.validation.model
                if mdl is None:
                    continue
                md = mdl.model_dump()
                digest: dict[str, Any] = {"schema_name": a.schema_name}
                if "title" in md:
                    digest["title_chars"] = len(str(md.get("title", "")))
                if "summary" in md:
                    digest["summary_chars"] = len(str(md.get("summary", "")))
                if isinstance(md.get("items"), list):
                    digest["faq_items"] = len(md["items"])
                if isinstance(md.get("chapters"), list):
                    digest["chapters"] = len(md["chapters"])
                if "episode_title" in md:
                    digest["episode_title_chars"] = len(str(md.get("episode_title", "")))
                artifact_digest.append(digest)
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=TRANSCRIPT_STAGE,
                status="completed",
                provider_name=ti_log_provider,
                model_name=ti_model,
                started_at=t0,
                finished_at=t1,
                input_tokens=ti_prov.input_tokens_total,
                output_tokens=ti_prov.output_tokens_total,
                cost_estimate_internal=ti_prov.cost_estimate_total or None,
                validation_status=ValidationStatus.ACCEPTED.value,
                error_code=None,
                error_message=None,
                provider_request_id=ti_prov.last_request_id,
                extra_json={
                    "chunks": len(chunks),
                    "live_openai_completions_used": live_used,
                    "artifact_digest": artifact_digest[:20],
                    "artifact_count": len(ti_artifacts),
                },
            )
        except TranscriptIntelligenceValidationError as exc:
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=TRANSCRIPT_STAGE,
                status="failed",
                provider_name=ti_log_provider,
                model_name=ti_model,
                started_at=t0,
                finished_at=t1,
                input_tokens=ti_prov.input_tokens_total,
                output_tokens=ti_prov.output_tokens_total,
                cost_estimate_internal=ti_prov.cost_estimate_total or None,
                validation_status=ValidationStatus.REJECTED.value,
                error_code="transcript_intelligence_validation",
                error_message=str(exc)[:2048],
                provider_request_id=ti_prov.last_request_id,
                extra_json=None,
            )
            log.warning("mock_ai_transcript_validation_failed job_id=%s err=%s", job.id, exc)
        except OpenAIHTTPAdapterError as exc:
            t1 = utcnow()
            _append_stage_log(
                session,
                ai_run_id=run_id,
                job_id=job.id,
                stage_name=TRANSCRIPT_STAGE,
                status="failed",
                provider_name="openai",
                model_name=ti_model,
                started_at=t0,
                finished_at=t1,
                input_tokens=ti_prov.input_tokens_total,
                output_tokens=ti_prov.output_tokens_total,
                cost_estimate_internal=ti_prov.cost_estimate_total or None,
                validation_status=None,
                error_code=exc.code,
                error_message=str(exc)[:2048],
                provider_request_id=ti_prov.last_request_id,
                extra_json=None,
            )
            log.warning("worker_enrichment_openai_http_failed job_id=%s code=%s", job.id, exc.code)

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
