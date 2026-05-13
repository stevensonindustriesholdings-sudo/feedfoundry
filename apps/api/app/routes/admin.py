from datetime import datetime, timezone
from uuid import uuid4

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import verify_internal_key
from app.db import get_session
from app.models import CreditTransaction, Job, ProviderConfig
from app.services import audit
from app.services.credit_ledger import admin_grant_processing_minutes, get_or_create_wallet
from app.services.processing_time import sum_goodwill_minutes_calendar_year

router = APIRouter(prefix="/admin", tags=["admin"])


class GrantProcessingMinutesBody(BaseModel):
    minutes: int = Field(ge=1, le=50000)
    memo: Optional[str] = None


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


@router.get("/organisations/{organisation_id}/processing")
def get_org_processing(
    organisation_id: str,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    wallet = get_or_create_wallet(session, organisation_id)
    session.refresh(wallet)
    y = datetime.now(timezone.utc).year
    goodwill_ytd = sum_goodwill_minutes_calendar_year(session, organisation_id, year=y)
    tx_limit = 100
    txns = session.exec(
        select(CreditTransaction)
        .where(CreditTransaction.organisation_id == organisation_id)
        .order_by(desc(CreditTransaction.created_at))
        .limit(tx_limit)
    ).all()
    return {
        "organisation_id": organisation_id,
        "processing_minutes_available": wallet.balance_available,
        "processing_minutes_reserved": wallet.balance_reserved,
        "processing_minutes_used_lifetime": wallet.balance_spent_lifetime,
        "goodwill_processing_minutes_granted_ytd": goodwill_ytd,
        "recent_transactions": [t.model_dump(mode="json") for t in txns],
    }


@router.post("/organisations/{organisation_id}/grant-processing-minutes")
def grant_processing_minutes(
    organisation_id: str,
    body: GrantProcessingMinutesBody,
    _: None = Depends(verify_internal_key),
    session: Session = Depends(get_session),
):
    key = f"ff:admin:grant:{organisation_id}:{uuid4().hex}"
    admin_grant_processing_minutes(
        session,
        organisation_id=organisation_id,
        minutes=body.minutes,
        idempotency_key=key,
        memo=body.memo,
    )
    session.commit()
    audit.log_admin_event(
        "admin_grant_processing_minutes",
        {"organisation_id": organisation_id, "minutes": body.minutes},
    )
    wallet = get_or_create_wallet(session, organisation_id)
    session.refresh(wallet)
    return {
        "ok": True,
        "processing_minutes_available": wallet.balance_available,
        "processing_minutes_reserved": wallet.balance_reserved,
    }


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
