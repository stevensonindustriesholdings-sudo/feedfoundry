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
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus
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
    reserve_processing_minutes,
)
from app.services import job_estimator
from app.settings import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
        items.append(
            JobSummaryItem(
                job_id=job.id,
                status=job.status.value,
                progress_percent=job.progress_percent,
                current_stage=job.current_stage,
                media_asset_id=job.media_asset_id,
                created_at=job.created_at.isoformat() if job.created_at else None,
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
        # Deprecated aliases preserved one release.
        estimated_credits=est,
        reserved_credits=resv,
        actual_credits_so_far=charged,
    )
