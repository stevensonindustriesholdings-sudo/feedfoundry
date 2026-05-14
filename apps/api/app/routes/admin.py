from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import AIRun, AIStageLog, Job, ProviderConfig
from app.schemas.ai_run_visibility import AIRunListEnvelope, AIRunVisibilityOut, AIStageVisibilityOut
from app.services import audit

router = APIRouter(prefix="/admin", tags=["admin"])


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


def _infer_provider_mode(stage_rows: List[AIStageLog]) -> Optional[str]:
    names = {
        s.provider_name.strip().lower()
        for s in stage_rows
        if s.provider_name and s.provider_name.strip()
    }
    if not names:
        return None
    if len(names) == 1:
        return next(iter(names))
    return "mixed"


def _stages_to_out(stage_rows: List[AIStageLog]) -> List[AIStageVisibilityOut]:
    ordered = sorted(stage_rows, key=lambda s: (s.created_at, s.id))
    return [
        AIStageVisibilityOut(
            id=s.id,
            stage_name=s.stage_name,
            status=s.status,
            provider_name=s.provider_name,
            model_name=s.model_name,
            started_at=s.started_at,
            finished_at=s.finished_at,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            cost_estimate_internal=s.cost_estimate_internal,
            validation_status=s.validation_status,
            error_code=s.error_code,
            error_message=s.error_message,
            provider_request_id=s.provider_request_id,
            created_at=s.created_at,
        )
        for s in ordered
    ]


def _run_to_out(run: AIRun, stage_rows: List[AIStageLog]) -> AIRunVisibilityOut:
    stages_out = _stages_to_out(stage_rows)
    return AIRunVisibilityOut(
        id=run.id,
        job_id=run.job_id,
        organisation_id=run.organisation_id,
        status=run.status,
        provider_mode=_infer_provider_mode(stage_rows),
        captain_plan_version=run.captain_plan_version,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        stage_count=len(stages_out),
        stages=stages_out,
    )


@router.get("/ai-runs", response_model=AIRunListEnvelope)
def list_ai_runs(
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
    organisation_id: Optional[str] = Query(None, description="Filter by organisation id."),
    job_id: Optional[str] = Query(None, description="Filter by job id."),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(AIRun).order_by(desc(AIRun.created_at))
    if organisation_id:
        stmt = stmt.where(AIRun.organisation_id == organisation_id)
    if job_id:
        stmt = stmt.where(AIRun.job_id == job_id)
    stmt = stmt.limit(limit)
    runs = list(session.exec(stmt).all())
    if not runs:
        audit.log_admin_event("admin_list_ai_runs", {"count": 0})
        return AIRunListEnvelope(ai_runs=[], count=0)
    run_ids = [r.id for r in runs]
    stages = list(
        session.exec(select(AIStageLog).where(AIStageLog.ai_run_id.in_(run_ids))).all()  # type: ignore[attr-defined]
    )
    by_run: dict[str, List[AIStageLog]] = {}
    for st in stages:
        by_run.setdefault(st.ai_run_id, []).append(st)
    items = [_run_to_out(r, by_run.get(r.id, [])) for r in runs]
    audit.log_admin_event("admin_list_ai_runs", {"count": len(items)})
    return AIRunListEnvelope(ai_runs=items, count=len(items))


@router.get("/ai-runs/{ai_run_id}", response_model=AIRunVisibilityOut)
def get_ai_run(
    ai_run_id: str,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    run = session.get(AIRun, ai_run_id)
    if not run:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="AI run not found.",
        )
    stages = list(
        session.exec(
            select(AIStageLog).where(AIStageLog.ai_run_id == run.id).order_by(AIStageLog.created_at)
        ).all()
    )
    audit.log_admin_event("admin_get_ai_run", {"ai_run_id": ai_run_id})
    return _run_to_out(run, stages)


@router.get("/jobs/{job_id}/ai-runs", response_model=AIRunListEnvelope)
def list_ai_runs_for_job(
    job_id: str,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
    organisation_id: Optional[str] = Query(
        None,
        description="When set, job must belong to this organisation (otherwise not found).",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    job = session.get(Job, job_id)
    if not job or (organisation_id and job.organisation_id != organisation_id):
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="Job not found.",
        )
    stmt = (
        select(AIRun)
        .where(AIRun.job_id == job_id)
        .order_by(desc(AIRun.created_at))
        .limit(limit)
    )
    runs = list(session.exec(stmt).all())
    if not runs:
        return AIRunListEnvelope(ai_runs=[], count=0)
    run_ids = [r.id for r in runs]
    stages = list(
        session.exec(select(AIStageLog).where(AIStageLog.ai_run_id.in_(run_ids))).all()  # type: ignore[attr-defined]
    )
    by_run: dict[str, List[AIStageLog]] = {}
    for st in stages:
        by_run.setdefault(st.ai_run_id, []).append(st)
    items = [_run_to_out(r, by_run.get(r.id, [])) for r in runs]
    audit.log_admin_event("admin_list_ai_runs_for_job", {"job_id": job_id, "count": len(items)})
    return AIRunListEnvelope(ai_runs=items, count=len(items))
