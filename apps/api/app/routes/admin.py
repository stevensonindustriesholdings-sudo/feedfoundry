from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import verify_internal_key
from app.db import get_session
from app.models import Job, ProviderConfig
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
