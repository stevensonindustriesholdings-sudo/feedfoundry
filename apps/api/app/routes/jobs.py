"""Job lifecycle API.

Integration: **frontend / proxy** → this router → **Postgres** (job rows, wallet
reservations) → **worker** polls jobs and writes ``job_outputs`` + manifest objects.

Reservations call ``credit_ledger.reserve_processing_minutes`` (D's foundation name);
responses use **processing minutes** for customer-visible fields. Legacy ``*_credits``
fields on the response are kept one release for backward compatibility and are
marked deprecated in OpenAPI.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import Job, JobOutput, JobOutputType, JobStatus, MediaAsset, MediaAssetStatus, YoutubeSourceQueue
from app.schemas.api import (
    CreateJobRequest,
    CreateJobResponse,
    JobListResponse,
    JobStatusResponse,
    JobSummaryItem,
)
from app.schemas.processing_display import processing_minutes_to_approx_hours
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import (
    CreditLedgerError,
    ledger_reserve_key,
    release_reserved_processing_minutes,
    reserve_processing_minutes,
)
from app.services import job_estimator
from app.services.evidence_visibility import visual_evidence_summary_for_job
from app.settings import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Job statuses that may be cancelled by an API caller. Anything else is either
# already CANCELLED (handled idempotently) or terminal (409 job_already_terminal).
_CANCELLABLE_STATUSES = {JobStatus.UPLOADED, JobStatus.QUEUED, JobStatus.PROCESSING}


def _job_status_response(job: Job, visual_evidence: dict | None = None) -> JobStatusResponse:
    """Build a canonical job status response (PM canonical + deprecated *_credits aliases)."""
    est = job.estimated_processing_minutes
    resv = job.reserved_processing_minutes
    charged = job.actual_processing_minutes_charged
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        estimated_processing_minutes=est,
        reserved_processing_minutes=resv,
        actual_processing_minutes_charged=charged,
        estimated_processing_hours=processing_minutes_to_approx_hours(est),
        visual_evidence=visual_evidence,
        failure_code=job.failure_code,
        failure_reason=job.failure_reason,
        failure_message=job.failure_message,
        estimated_credits=est,
        reserved_credits=resv,
        actual_credits_so_far=charged,
    )


def _output_presence_for_job(session: Session, *, organisation_id: str, job_id: str) -> dict[str, bool]:
    rows = session.exec(select(JobOutput.output_type).where(JobOutput.job_id == job_id)).all()
    output_types = {row.value for row in rows if isinstance(row, JobOutputType)}
    visual_evidence = visual_evidence_summary_for_job(
        session,
        organisation_id=organisation_id,
        job_id=job_id,
    )
    return {
        "has_transcript": JobOutputType.RAW_TRANSCRIPT.value in output_types
        or JobOutputType.CLEAN_TRANSCRIPT.value in output_types,
        "has_agent_bundle": JobOutputType.AGENT_BUNDLE.value in output_types,
        "has_hosted_manifest": JobOutputType.HOSTED_MANIFEST.value in output_types,
        "has_export_bundle": JobOutputType.EXPORT_BUNDLE.value in output_types,
        "has_visual_evidence": bool(visual_evidence and visual_evidence.get("artifact_available")),
    }


@router.get("", response_model=JobListResponse)
def list_jobs(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> JobListResponse:
    """Poll-friendly job list for the organisation (newest first)."""
    filters: list = [Job.organisation_id == organisation_id]
    if status_filter:
        try:
            st = JobStatus(status_filter)
        except ValueError:
            raise problem(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="invalid_job_status",
                message=f"Unknown job status filter: {status_filter!r}.",
            )
        filters.append(Job.status == st)

    total = session.exec(select(func.count()).select_from(Job).where(*filters)).one()
    stmt = (
        select(Job)
        .where(*filters)
        .order_by(desc(Job.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    items: list[JobSummaryItem] = []
    for job in rows:
        media = session.get(MediaAsset, job.media_asset_id)
        yt_row = session.exec(select(YoutubeSourceQueue).where(YoutubeSourceQueue.job_id == job.id)).first()
        source_kind = (
            "youtube"
            if yt_row or (media and media.intake_kind.startswith("youtube"))
            else ("upload" if media else None)
        )
        source_title = yt_row.source_title if yt_row else None
        source_duration_seconds = (
            yt_row.source_duration_seconds
            if yt_row and yt_row.source_duration_seconds is not None
            else (media.duration_seconds if media else None)
        )
        items.append(
            JobSummaryItem(
                job_id=job.id,
                status=job.status.value,
                progress_percent=job.progress_percent,
                current_stage=job.current_stage,
                media_asset_id=job.media_asset_id,
                created_at=job.created_at.isoformat() if job.created_at else None,
                source_kind=source_kind,
                source_title=source_title,
                source_duration_seconds=source_duration_seconds,
                acquisition_status=yt_row.acquisition_status if yt_row else None,
                acquisition_error=yt_row.acquisition_error if yt_row else None,
                **_output_presence_for_job(session, organisation_id=organisation_id, job_id=job.id),
            )
        )
    return JobListResponse(jobs=items, total=int(total))


@router.post("", response_model=CreateJobResponse)
def create_job(
    body: CreateJobRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> CreateJobResponse:
    if not annual_access_svc.has_active_processing_entitlement(session, organisation_id):
        raise problem(
            status_code=status.HTTP_403_FORBIDDEN,
            code="annual_archive_access_required",
            message="Active annual hosted archive access is required to create jobs.",
        )

    ma = session.get(MediaAsset, body.media_asset_id)
    if not ma or ma.organisation_id != organisation_id:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="media_asset_not_found",
            message="Media asset not found for this organisation.",
        )

    if ma.status in (MediaAssetStatus.REJECTED, MediaAssetStatus.ARCHIVED):
        raise problem(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="media_asset_invalid_state",
            message="This media asset cannot be processed in its current state.",
        )

    est = job_estimator.estimate_job_processing_minutes(
        routing_path=get_settings().ai_routing_config_path,
        requested_outputs=body.requested_outputs,
        media_duration_seconds=ma.duration_seconds,
    )

    job = Job(
        organisation_id=organisation_id,
        media_asset_id=ma.id,
        media_kind=ma.media_type,
        source_content_type=ma.upload_content_type,
        status=JobStatus.UPLOADED,
        requested_outputs_json=list(body.requested_outputs),
        distribution_targets_json=list(body.distribution_targets or []),
        estimated_processing_minutes=est,
    )
    session.add(job)
    session.flush()

    try:
        reserve_processing_minutes(
            session,
            organisation_id=organisation_id,
            job_id=job.id,
            amount=est,
            idempotency_key=ledger_reserve_key(job.id),
        )
    except CreditLedgerError as e:
        if str(e) == "insufficient_processing_allowance":
            session.rollback()
            raise problem(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="insufficient_processing_allowance",
                message="Not enough processing minutes available to reserve this job.",
            )
        session.rollback()
        raise problem(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="processing_allowance_reservation_failed",
            message="Could not reserve processing minutes for this job.",
        )

    job.status = JobStatus.QUEUED
    job.reserved_processing_minutes = est
    session.add(job)
    session.commit()
    session.refresh(job)

    return CreateJobResponse(
        job_id=job.id,
        status=job.status.value,
        estimated_processing_minutes=est,
        reserved_processing_minutes=est,
        estimated_processing_hours=processing_minutes_to_approx_hours(est) or 0.0,
        # Deprecated aliases preserved one release.
        estimated_credits=est,
        reserved_credits=est,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> JobStatusResponse:
    job = session.get(Job, job_id)
    if not job or job.organisation_id != organisation_id:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="Job not found for this organisation.",
        )
    visual_evidence = visual_evidence_summary_for_job(
        session,
        organisation_id=organisation_id,
        job_id=job_id,
    )
    return _job_status_response(job, visual_evidence=visual_evidence)


@router.post("/{job_id}/cancel", response_model=JobStatusResponse)
def cancel_job(
    job_id: str,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> JobStatusResponse:
    """
    Cancel a non-terminal job. Releases any reserved processing minutes that
    have not yet been charged (failed/cancelled jobs must not consume the
    annual processing allowance). Idempotent: cancelling an already-cancelled
    job returns 200 with the current state; cancelling a completed or failed
    job returns 409 ``job_already_terminal``.
    """
    job = session.get(Job, job_id)
    if not job or job.organisation_id != organisation_id:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="Job not found for this organisation.",
        )

    if job.status == JobStatus.CANCELLED:
        return _job_status_response(job)

    if job.status not in _CANCELLABLE_STATUSES:
        raise problem(
            status_code=status.HTTP_409_CONFLICT,
            code="job_already_terminal",
            message=f"Job is already in terminal state '{job.status.value}'.",
        )

    reserved = int(job.reserved_processing_minutes or 0)
    charged = int(job.actual_processing_minutes_charged or 0)

    job.status = JobStatus.CANCELLED
    session.add(job)

    if reserved > 0 and charged == 0:
        try:
            release_reserved_processing_minutes(
                session,
                organisation_id=organisation_id,
                job_id=job.id,
                amount=reserved,
                idempotency_key=f"ff:job:{job.id}:cancel",
            )
        except CreditLedgerError as e:
            session.rollback()
            raise problem(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="processing_allowance_release_failed",
                message=f"Could not release reserved processing minutes on cancel: {e}",
            )

    session.commit()
    session.refresh(job)
    return _job_status_response(job)
