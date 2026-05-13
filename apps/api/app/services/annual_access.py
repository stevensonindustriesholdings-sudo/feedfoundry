from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlmodel import Session, select

from app.models import AnnualAccess, AnnualAccessStatus


def has_active_processing_entitlement(session: Session, organisation_id: str) -> bool:
    """
    Annual hosted archive / access entitles the org to run processing jobs (V1 slice).
    Active or grace periods allow job creation.
    """
    stmt = (
        select(AnnualAccess)
        .where(AnnualAccess.organisation_id == organisation_id)
        .where(
            AnnualAccess.status.in_(
                [
                    AnnualAccessStatus.ACTIVE,
                    AnnualAccessStatus.GRACE,
                ]
            )
        )
        .order_by(desc(AnnualAccess.period_end))
    )
    return session.exec(stmt).first() is not None


def access_inactive_exception() -> HTTPException:
    """Customer-facing annual access gate (see docs/MVP_PARALLEL_CONTRACT.md)."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "ACCESS_INACTIVE",
            "message": "Annual access is required to upload and process media.",
        },
    )


def get_latest_annual_access(
    session: Session, organisation_id: str
) -> Optional[AnnualAccess]:
    stmt = (
        select(AnnualAccess)
        .where(AnnualAccess.organisation_id == organisation_id)
        .order_by(desc(AnnualAccess.period_end))
    )
    return session.exec(stmt).first()
