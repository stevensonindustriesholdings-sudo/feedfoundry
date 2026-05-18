from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.db import get_session
from app.http_errors import problem
from app.services.manifest_writer import find_manifest_payload
from app.services.evidence_visibility import public_hosted_manifest_payload, visual_evidence_summary_from_manifest

router = APIRouter(prefix="/manifests", tags=["manifests"])


@router.get("/{creator_slug}/{asset_slug}.json")
def get_hosted_manifest(
    creator_slug: str,
    asset_slug: str,
    session: Session = Depends(get_session),
):
    payload = find_manifest_payload(session, creator_slug=creator_slug, asset_slug=asset_slug)
    if not payload:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manifest_not_found",
            message="Hosted manifest not found for this slug pair.",
        )
    public_payload = public_hosted_manifest_payload(payload)
    evidence = visual_evidence_summary_from_manifest(payload)
    if evidence:
        for field in (
            "evidence_status",
            "visual_evidence_available",
            "transcript_evidence_available",
            "unsupported_claim_count",
            "human_review_required",
            "final_evidence_confidence",
            "visual_evidence_package_uri",
            "evidence_gate_reason",
        ):
            public_payload[field] = evidence.get(field)
    return JSONResponse(content=public_payload)
