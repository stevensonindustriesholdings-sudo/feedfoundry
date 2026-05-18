from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import JobOutput, JobOutputType

VISUAL_EVIDENCE_OUTPUT_TYPE = "visual_evidence"

_EVIDENCE_FIELDS = (
    "evidence_status",
    "visual_evidence_available",
    "transcript_evidence_available",
    "unsupported_claim_count",
    "human_review_required",
    "final_evidence_confidence",
    "visual_evidence_package_uri",
    "evidence_gate_reason",
)

_INTERNAL_VISUAL_PACKAGE_FIELDS = {
    "visual_evidence_package_object",
}


def hosted_manifest_for_job(session: Session, *, organisation_id: str, job_id: str) -> JobOutput | None:
    stmt = select(JobOutput).where(
        JobOutput.job_id == job_id,
        JobOutput.organisation_id == organisation_id,
        JobOutput.output_type == JobOutputType.HOSTED_MANIFEST,
    )
    return session.exec(stmt).first()


def public_hosted_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return public manifest JSON without the raw internal visual-evidence package."""
    return {k: v for k, v in payload.items() if k not in _INTERNAL_VISUAL_PACKAGE_FIELDS}


def visual_evidence_summary_from_manifest(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    visual_artifact = artifacts.get(VISUAL_EVIDENCE_OUTPUT_TYPE) if isinstance(artifacts, dict) else None
    artifact_uri = None
    if isinstance(visual_artifact, dict):
        artifact_uri = visual_artifact.get("storage_key")
    if not artifact_uri:
        artifact_uri = payload.get("visual_evidence_package_uri")
    artifact_available = bool(artifact_uri and isinstance(visual_artifact, dict))

    has_evidence_fields = any(field in payload for field in _EVIDENCE_FIELDS)
    if not has_evidence_fields and not artifact_available:
        return None

    status = payload.get("evidence_status")
    if not status:
        status = "needs_review" if artifact_available else "unavailable"

    return {
        "evidence_status": status,
        "visual_evidence_available": payload.get("visual_evidence_available"),
        "transcript_evidence_available": payload.get("transcript_evidence_available"),
        "unsupported_claim_count": payload.get("unsupported_claim_count"),
        "human_review_required": payload.get("human_review_required"),
        "final_evidence_confidence": payload.get("final_evidence_confidence"),
        "visual_evidence_package_uri": artifact_uri if artifact_available else None,
        "evidence_gate_reason": payload.get("evidence_gate_reason") or [],
        "artifact_available": artifact_available,
    }


def visual_evidence_summary_for_job(
    session: Session,
    *,
    organisation_id: str,
    job_id: str,
) -> dict[str, Any] | None:
    row = hosted_manifest_for_job(session, organisation_id=organisation_id, job_id=job_id)
    if not row or not row.json_payload:
        return None
    return visual_evidence_summary_from_manifest(row.json_payload)
