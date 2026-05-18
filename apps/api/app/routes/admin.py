from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import verify_internal_key
from app.config.env_validation import _stripped
from app.db import get_session
from app.http_errors import problem
from app.models import Job, JobOutput, JobOutputType, ProviderConfig, YoutubeSourceQueue
from app.services import audit
from app.services import storage as storage_service
from app.services.evidence_visibility import visual_evidence_summary_for_job

router = APIRouter(prefix="/admin", tags=["admin"])


def _agent_bundle_admin_api_enabled() -> bool:
    return _stripped(os.environ.get("FF_AGENT_BUNDLE_ADMIN_API_ENABLED", "")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@router.get("/youtube-queue")
def admin_list_youtube_queue(
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
    limit: int = 100,
):
    stmt = select(YoutubeSourceQueue).order_by(desc(YoutubeSourceQueue.created_at)).limit(limit)
    rows = session.exec(stmt).all()
    audit.log_admin_event("admin_list_youtube_queue", {"count": len(rows)})
    return {
        "items": [
            {
                "id": r.id,
                "organisation_id": r.organisation_id,
                "youtube_url": r.youtube_url,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/jobs")
def list_jobs(
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
    limit: int = 50,
):
    stmt = select(Job).limit(limit)
    jobs = session.exec(stmt).all()
    audit.log_admin_event("admin_list_jobs", {"count": len(jobs)})
    return {"jobs": [j.model_dump(mode="json") for j in jobs]}


@router.get("/provider-configs")
def list_provider_configs(
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    rows = session.exec(select(ProviderConfig)).all()
    return {"provider_configs": [r.model_dump(mode="json") for r in rows]}


@router.post("/provider-configs")
def upsert_provider_config(
    body: dict,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    allowed = {f for f in ProviderConfig.model_fields if f != "id"}
    pid = body.get("id")
    payload = {k: v for k, v in body.items() if k in allowed}
    if pid:
        row = session.get(ProviderConfig, pid)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
        for k, v in payload.items():
            setattr(row, k, v)
        session.add(row)
    else:
        row = ProviderConfig(**payload)
        session.add(row)
    session.commit()
    return {"ok": True}


@router.get("/jobs/{job_id}/evidence")
def admin_get_job_evidence(
    job_id: str,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    """Read visual-evidence readiness from hosted manifest output entries, not a DB enum row."""
    job = session.get(Job, job_id)
    if not job:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    evidence = visual_evidence_summary_for_job(
        session,
        organisation_id=job.organisation_id,
        job_id=job_id,
    )
    if not evidence:
        evidence = {"evidence_status": "unavailable", "artifact_available": False, "visual_evidence_package_uri": None}
    audit.log_admin_event("admin_get_job_evidence", {"job_id": job_id, "evidence_status": evidence.get("evidence_status")})
    return evidence


@router.get("/jobs/{job_id}/agent-bundle")
def admin_get_agent_bundle_json(
    job_id: str,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    """Read-only operator access to persisted ``agent_bundle.json`` (object storage)."""
    if not _agent_bundle_admin_api_enabled():
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    job = session.get(Job, job_id)
    if not job:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    stmt = select(JobOutput).where(
        JobOutput.job_id == job_id,
        JobOutput.output_type == JobOutputType.AGENT_BUNDLE,
    )
    row = session.exec(stmt).first()
    if not row or not row.storage_key:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    if not storage_service.storage_client_ready():
        raise problem(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="storage_not_configured",
            message="Object storage is not configured.",
        )
    raw = storage_service.get_object_bytes(
        bucket=storage_service.bucket_for_outputs(),
        key=row.storage_key,
    )
    if raw is None:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Not found.",
        )
    audit.log_admin_event("admin_get_agent_bundle_json", {"job_id": job_id})
    return JSONResponse(content=data)
