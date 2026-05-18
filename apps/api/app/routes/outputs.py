from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.config.env_validation import is_strict_deployment_env
from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.http_errors import problem
from app.models import Job, JobOutput, JobOutputType
from app.schemas.api import (
    JobOutputsCatalogResponse,
    JobOutputsResponse,
    OutputCatalogEntryResponse,
    OutputItemResponse,
)
from app.services import storage as storage_service
from app.services.evidence_visibility import (
    VISUAL_EVIDENCE_OUTPUT_TYPE,
    hosted_manifest_for_job,
    visual_evidence_summary_from_manifest,
)
from app.settings import get_settings

router = APIRouter(tags=["outputs"])

_OUTPUT_TITLES: dict[str, str] = {
    "raw_transcript": "Transcript",
    "clean_transcript": "Clean transcript",
    "chapters": "Chapters",
    "clip_candidates": "Clip candidates",
    "show_notes": "Show notes",
    "metadata": "Metadata",
    "ctas": "CTAs",
    "fact_sheet": "Fact Sheet",
    "faqs": "FAQs",
    "hosted_manifest": "Hosted Manifest",
    "export_bundle": "Export bundle",
    "media_inspection": "Media inspection",
    "agent_bundle": "Agent bundle",
    "visual_evidence": "Visual evidence",
}

_CATALOG_ORDER: list[JobOutputType] = [
    JobOutputType.RAW_TRANSCRIPT,
    JobOutputType.CLEAN_TRANSCRIPT,
    JobOutputType.CHAPTERS,
    JobOutputType.CLIP_CANDIDATES,
    JobOutputType.SHOW_NOTES,
    JobOutputType.METADATA,
    JobOutputType.CTAS,
    JobOutputType.FACT_SHEET,
    JobOutputType.FAQS,
    JobOutputType.HOSTED_MANIFEST,
    JobOutputType.EXPORT_BUNDLE,
    JobOutputType.AGENT_BUNDLE,
]


def _format_for_output(out: JobOutput) -> str:
    if out.json_payload is not None:
        return "json"
    if out.markdown_payload is not None:
        return "markdown"
    if out.html_payload is not None:
        return "html"
    if out.storage_key:
        return "json"
    return "markdown"


def _download_for_storage_key(*, storage_key: str) -> str:
    return storage_service.presign_get_for_key(
        storage_key=storage_key,
        download_filename=os.path.basename(storage_key),
    )


def _download_for_row(
    *,
    organisation_id: str,
    job_id: str,
    row: JobOutput,
) -> str:
    download_name = None
    if row.storage_key:
        download_name = os.path.basename(row.storage_key)
    return storage_service.presign_get_for_key(
        storage_key=row.storage_key
        or f"orgs/{organisation_id}/jobs/{job_id}/outputs/missing.json",
        download_filename=download_name,
    )


def _get_job_or_404(session: Session, organisation_id: str, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job or job.organisation_id != organisation_id:
        raise problem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="Job not found for this organisation.",
        )
    return job


@router.get("/jobs/{job_id}/outputs", response_model=JobOutputsResponse)
def list_job_outputs(
    job_id: str,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> JobOutputsResponse:
    _get_job_or_404(session, organisation_id, job_id)

    settings = get_settings()
    if is_strict_deployment_env(settings.app_env) and not storage_service.storage_client_ready(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "storage_not_configured",
                "message": "Object storage is not configured; output download URLs cannot be signed.",
            },
        )

    stmt = select(JobOutput).where(JobOutput.job_id == job_id, JobOutput.organisation_id == organisation_id)
    rows = session.exec(stmt).all()
    items: list[OutputItemResponse] = []
    for row in rows:
        items.append(
            OutputItemResponse(
                type=row.output_type.value,
                title=_OUTPUT_TITLES.get(row.output_type.value, row.output_type.value),
                format=_format_for_output(row),
                download_url=_download_for_row(
                    organisation_id=organisation_id, job_id=job_id, row=row
                ),
            )
        )
    manifest_row = hosted_manifest_for_job(session, organisation_id=organisation_id, job_id=job_id)
    evidence = visual_evidence_summary_from_manifest(manifest_row.json_payload if manifest_row else None)
    if evidence and evidence.get("artifact_available") and evidence.get("visual_evidence_package_uri"):
        items.append(
            OutputItemResponse(
                type=VISUAL_EVIDENCE_OUTPUT_TYPE,
                title=_OUTPUT_TITLES[VISUAL_EVIDENCE_OUTPUT_TYPE],
                format="json",
                download_url=_download_for_storage_key(storage_key=evidence["visual_evidence_package_uri"]),
                evidence_status=evidence.get("evidence_status"),
                artifact_available=True,
            )
        )
    return JobOutputsResponse(job_id=job_id, outputs=items)


@router.get("/jobs/{job_id}/outputs/catalog", response_model=JobOutputsCatalogResponse)
def catalog_job_outputs(
    job_id: str,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> JobOutputsCatalogResponse:
    """Doctrine-aligned slots; ``ready`` reflects persisted ``job_outputs`` rows."""
    _get_job_or_404(session, organisation_id, job_id)
    stmt = select(JobOutput).where(JobOutput.job_id == job_id, JobOutput.organisation_id == organisation_id)
    rows = {r.output_type: r for r in session.exec(stmt).all()}
    entries: list[OutputCatalogEntryResponse] = []
    manifest_row = rows.get(JobOutputType.HOSTED_MANIFEST)
    evidence = visual_evidence_summary_from_manifest(manifest_row.json_payload if manifest_row else None)
    for ot in _CATALOG_ORDER:
        row = rows.get(ot)
        if row:
            entries.append(
                OutputCatalogEntryResponse(
                    output_type=ot.value,
                    title=_OUTPUT_TITLES.get(ot.value, ot.value),
                    ready=True,
                    format=_format_for_output(row),
                    download_url=_download_for_row(
                        organisation_id=organisation_id, job_id=job_id, row=row
                    ),
                )
            )
        else:
            entries.append(
                OutputCatalogEntryResponse(
                    output_type=ot.value,
                    title=_OUTPUT_TITLES.get(ot.value, ot.value),
                    ready=False,
                    format=None,
                    download_url=None,
                )
            )
    if evidence:
        uri = evidence.get("visual_evidence_package_uri")
        artifact_available = bool(evidence.get("artifact_available") and uri)
        download_url = _download_for_storage_key(storage_key=str(uri)) if artifact_available else None
        entries.append(
            OutputCatalogEntryResponse(
                output_type=VISUAL_EVIDENCE_OUTPUT_TYPE,
                title=_OUTPUT_TITLES[VISUAL_EVIDENCE_OUTPUT_TYPE],
                ready=artifact_available,
                format="json" if artifact_available else None,
                download_url=download_url,
                evidence_status=evidence.get("evidence_status"),
                artifact_available=artifact_available,
                human_review_required=evidence.get("human_review_required"),
                final_evidence_confidence=evidence.get("final_evidence_confidence"),
            )
        )
    return JobOutputsCatalogResponse(job_id=job_id, outputs=entries)
