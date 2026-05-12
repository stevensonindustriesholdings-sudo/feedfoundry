from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models import Job, JobOutput, JobOutputType, MediaAsset


def find_manifest_payload(
    session: Session,
    *,
    creator_slug: str,
    asset_slug: str,
) -> Optional[Dict[str, Any]]:
    stmt = select(MediaAsset).where(
        MediaAsset.creator_slug == creator_slug,
        MediaAsset.asset_slug == asset_slug,
    )
    asset = session.exec(stmt).first()
    if not asset:
        return None
    stmt_out = (
        select(JobOutput)
        .join(Job, JobOutput.job_id == Job.id)
        .where(
            Job.media_asset_id == asset.id,
            JobOutput.output_type == JobOutputType.HOSTED_MANIFEST,
        )
        .order_by(desc(Job.completed_at), desc(JobOutput.created_at))
    )
    for out in session.exec(stmt_out).all():
        if out.json_payload:
            return out.json_payload
    return None
