from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus
from app.schemas.api import CreateJobRequest, CreateJobResponse, JobStatusResponse
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import CreditLedgerError, ledger_reserve_key, reserve_processing_minutes
from app.services import job_estimator
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="insufficient_credits",
            )
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="processing_allowance_reservation_failed",
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
    charged = job.actual_processing_minutes_charged
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        estimated_processing_minutes=job.estimated_processing_minutes,
        reserved_processing_minutes=job.reserved_processing_minutes,
        actual_processing_minutes_charged=charged,
        estimated_credits=job.estimated_processing_minutes,
        reserved_credits=job.reserved_processing_minutes,
        actual_credits_so_far=charged,
    )
