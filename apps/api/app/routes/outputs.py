from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import require_organisation_id, verify_internal_key
from app.db import get_session
from app.models import Job, JobOutput
from app.schemas.api import JobOutputsResponse, OutputItemResponse
from app.services import storage as storage_service

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
}


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


@router.get("/jobs/{job_id}/outputs", response_model=JobOutputsResponse)
def list_job_outputs(
    job_id: str,
    _: None = Depends(verify_internal_key),
    organisation_id: str = Depends(require_organisation_id),
    session: Session = Depends(get_session),
) -> JobOutputsResponse:
    job = session.get(Job, job_id)
    if not job or job.organisation_id != organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    stmt = select(JobOutput).where(JobOutput.job_id == job_id, JobOutput.organisation_id == organisation_id)
    rows = session.exec(stmt).all()
    items: list[OutputItemResponse] = []
    for row in rows:
        download_name = None
        if row.storage_key:
            download_name = os.path.basename(row.storage_key)
        dl = storage_service.presign_get_for_key(
            storage_key=row.storage_key or f"orgs/{organisation_id}/jobs/{job_id}/outputs/missing.json",
            download_filename=download_name,
        )
        items.append(
            OutputItemResponse(
                type=row.output_type.value,
                title=_OUTPUT_TITLES.get(row.output_type.value, row.output_type.value),
                format=_format_for_output(row),
                download_url=dl,
            )
        )
    return JobOutputsResponse(job_id=job_id, outputs=items)
