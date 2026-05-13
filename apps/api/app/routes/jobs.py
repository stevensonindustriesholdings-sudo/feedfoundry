"""Job lifecycle API.

Integration: **frontend / proxy** → this router → **Postgres** (job rows, wallet
reservations) → **worker** polls jobs and writes ``job_outputs`` + manifest objects.

Reservations use ``credit_ledger.reserve_credits`` (internal name); responses use
**processing minutes** for customer-visible fields.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus
from app.schemas.api import (
    CreateJobRequest,
    CreateJobResponse,
    JobListResponse,
    JobStatusResponse,
    JobSummaryItem,
)
from app.schemas.processing_display import ledger_units_as_processing_minutes, processing_minutes_to_approx_hours
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import CreditLedgerError, ledger_reserve_key, reserve_credits
from app.services import job_estimator
from app.settings import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
    limit: int = 25,
) -> JobListResponse:
    lim = max(1, min(limit, 100))
    stmt = (
        select(Job)
        .where(Job.organisation_id == organisation_id)
        .order_by(desc(Job.created_at))
        .limit(lim)
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
    return JobListResponse(jobs=items)


@router.post("", response_model=CreateJobResponse)
def create_job(
    body: CreateJobRequest,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> CreateJobResponse:
    if not annual_access_svc.has_active_processing_entitlement(session, organisation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "annual_archive_access_required",
                "message": "Active annual hosted archive access is required to create jobs.",
            },
        )

    ma = session.get(MediaAsset, body.media_asset_id)
    if not ma or ma.organisation_id != organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="media_asset_not_found")

    if ma.status in (MediaAssetStatus.REJECTED, MediaAssetStatus.ARCHIVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_asset_invalid_state",
        )

    est = job_estimator.estimate_job_credits(
        routing_path=get_settings().ai_routing_config_path,
        requested_outputs=body.requested_outputs,
        media_duration_seconds=ma.duration_seconds,
    )

    job = Job(
        organisation_id=organisation_id,
        media_asset_id=ma.id,
        status=JobStatus.CREATED,
        requested_outputs_json=list(body.requested_outputs),
        distribution_targets_json=list(body.distribution_targets or []),
        estimated_credits=est,
    )
    session.add(job)
    session.flush()

    try:
        reserve_credits(
            session,
            organisation_id=organisation_id,
            job_id=job.id,
            amount=est,
            idempotency_key=ledger_reserve_key(job.id),
        )
    except CreditLedgerError as e:
        if str(e) == "insufficient_available_credits":
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "insufficient_processing_allowance",
                    "message": "Not enough processing minutes available to reserve this job.",
                },
            )
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "processing_allowance_reservation_failed",
                "message": "Could not reserve processing minutes for this job.",
            },
        )

    job.status = JobStatus.QUEUED
    job.reserved_credits = est
    session.add(job)
    session.commit()
    session.refresh(job)

    return CreateJobResponse(
        job_id=job.id,
        status=job.status.value,
        estimated_processing_minutes=est,
        reserved_processing_minutes=est,
        estimated_processing_hours=processing_minutes_to_approx_hours(est) or 0.0,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    est = ledger_units_as_processing_minutes(job.estimated_credits)
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        estimated_processing_minutes=est,
        reserved_processing_minutes=ledger_units_as_processing_minutes(job.reserved_credits),
        processing_minutes_consumed_so_far=ledger_units_as_processing_minutes(job.actual_credits),
        estimated_processing_hours=processing_minutes_to_approx_hours(est),
    )
