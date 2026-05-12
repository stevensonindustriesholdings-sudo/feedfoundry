from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.schemas.api import AccountCreditsResponse
from app.services import annual_access as annual_access_svc
from app.services.credit_ledger import get_or_create_wallet

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/credits", response_model=AccountCreditsResponse)
def get_credits(
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> AccountCreditsResponse:
    wallet = get_or_create_wallet(session, organisation_id)
    aa = annual_access_svc.get_latest_annual_access(session, organisation_id)
    if not aa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="annual_access_not_configured",
        )
    return AccountCreditsResponse(
        annual_access_status=aa.status.value,
        hosting_until=aa.hosting_until.date().isoformat() if aa.hosting_until else None,
        credits_available=wallet.balance_available,
        credits_reserved=wallet.balance_reserved,
        credits_spent_lifetime=wallet.balance_spent_lifetime,
        next_credit_expiry=aa.period_end.date().isoformat(),
    )
