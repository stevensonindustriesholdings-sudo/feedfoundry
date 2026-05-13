from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus
from app.schemas.api import CreateJobRequest, CreateJobResponse, JobStatusResponse
from app.services import annual_access as annual_access_svc
from app.services import processing_time as processing_time_svc
from app.services.job_estimator import estimate_job_processing_minutes
from app.services.processing_time import ProcessingReservationBlocked
from app.settings import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
            detail="annual_access_required",
        )

    ma = session.get(MediaAsset, body.media_asset_id)
    if not ma or ma.organisation_id != organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="media_asset_not_found")

    if ma.status in (MediaAssetStatus.REJECTED, MediaAssetStatus.ARCHIVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_asset_invalid_state",
        )

    settings = get_settings()
    est = estimate_job_processing_minutes(
        routing_path=settings.ai_routing_config_path,
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

    outcome = processing_time_svc.reserve_processing_time_for_job(
        session,
        organisation_id=organisation_id,
        job_id=job.id,
        estimated_minutes=est,
        settings=settings,
    )
    if isinstance(outcome, ProcessingReservationBlocked):
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "allowed": False,
                "error": outcome.error,
                "message": outcome.message,
                "available_minutes": outcome.available_minutes,
                "estimated_minutes": outcome.estimated_minutes,
                "shortfall_minutes": outcome.shortfall_minutes,
            },
        )

    job.status = JobStatus.QUEUED
    job.reserved_credits = est
    if outcome.goodwill_minutes > 0:
        job.goodwill_minutes_granted = outcome.goodwill_minutes
    session.add(job)
    session.commit()
    session.refresh(job)

    warn = outcome.goodwill_minutes > 0
    msg = (
        f"We covered {outcome.goodwill_minutes} extra minutes for this upload."
        if warn
        else None
    )
    return CreateJobResponse(
        job_id=job.id,
        status=job.status.value,
        allowed=True,
        warning=warn,
        message=msg,
        available_minutes=outcome.available_minutes_before,
        estimated_minutes=est,
        goodwill_minutes=outcome.goodwill_minutes if warn else None,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    est = job.estimated_credits
    res = job.reserved_credits
    act = job.actual_credits
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        estimated_credits=est,
        reserved_credits=res,
        actual_credits_so_far=act,
        goodwill_minutes_granted=job.goodwill_minutes_granted,
        estimated_processing_minutes=est,
        reserved_processing_minutes=res,
        processing_minutes_used_so_far=act,
    )
