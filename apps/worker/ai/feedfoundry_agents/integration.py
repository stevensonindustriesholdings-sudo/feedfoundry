"""Worker hook: run deterministic FeedFoundry agent bundle after transcript + FFmpeg-derived inspection."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle
from ai.feedfoundry_agents.schemas import (
    FeedFoundryJobInput,
    MediaMetaIn,
    ProductContextIn,
    TranscriptPayloadIn,
    TranscriptSegmentIn,
    VisualFrameIn,
)
from app.models import Job, JobOutput, JobOutputType, MediaAsset
from app.services.storage import job_output_object_key, put_json_bytes
from pipeline.errors import JobProcessingFailure
from sqlmodel import Session

log = logging.getLogger("feedfoundry.worker.agent_bundle")

ENV_FLAG = "FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED"


def feedfoundry_agent_bundle_enabled() -> bool:
    """Opt-in only; default off preserves pre-wire worker behaviour."""
    return os.environ.get(ENV_FLAG, "").lower() in ("1", "true", "yes")


def build_feedfoundry_job_input_from_worker(
    *,
    job: Job,
    media: MediaAsset,
    transcript_payload: dict[str, Any],
    media_inspection_payload: dict[str, Any] | None,
) -> FeedFoundryJobInput:
    """Map worker artefacts to ``FeedFoundryJobInput`` (strict Pydantic)."""
    segments_raw = transcript_payload.get("segments") or []
    segments = [
        TranscriptSegmentIn(
            start=float(s.get("start", 0.0)),
            end=float(s.get("end", 0.0)),
            text=str(s.get("text") or ""),
        )
        for s in segments_raw
    ]
    transcript = TranscriptPayloadIn(
        schema_version=str(transcript_payload.get("schema_version") or "1.0"),
        segments=segments,
    )
    visual_frames = visual_frames_from_media_inspection(media_inspection_payload)
    mi = media_inspection_payload or {}
    dur = mi.get("duration_seconds")
    duration_seconds: float | None
    try:
        duration_seconds = float(dur) if dur is not None else None
    except (TypeError, ValueError):
        duration_seconds = None
    cf_raw = mi.get("container_format")
    container_format = str(cf_raw).split(",")[0].strip() if cf_raw else None
    media_meta = MediaMetaIn(
        duration_seconds=duration_seconds,
        container_format=container_format or None,
    )
    base_name = (media.original_filename or "episode").rsplit(".", 1)[0]
    product = ProductContextIn(show_name=base_name, niche="", primary_topics=[])
    return FeedFoundryJobInput(
        job_id=job.id,
        organisation_id=job.organisation_id,
        media_asset_id=media.id,
        creator_slug=media.creator_slug or "unknown-creator",
        asset_slug=media.asset_slug or "episode",
        original_basename=media.original_filename,
        transcript=transcript,
        visual_frames=visual_frames,
        product_context=product,
        media_meta=media_meta,
        ffmpeg_failure=None,
    )


def visual_frames_from_media_inspection(mi: dict[str, Any] | None) -> list[VisualFrameIn]:
    """Derive sparse timeline anchors from FFmpeg/ffprobe chunk plan (no real keyframe URIs yet)."""
    if not mi:
        return []
    plan = mi.get("chunk_plan") or []
    out: list[VisualFrameIn] = []
    for row in plan[:24]:
        out.append(
            VisualFrameIn(
                t_seconds=float(row.get("start_sec", 0.0)),
                label=f"chunk_{row.get('index', len(out))}",
                frame_uri=None,
            )
        )
    if not out:
        try:
            d = float(mi.get("duration_seconds") or 0.0)
        except (TypeError, ValueError):
            d = 0.0
        if d > 0.0:
            out.append(VisualFrameIn(t_seconds=0.0, label="t0", frame_uri=None))
    return out


def maybe_write_agent_bundle(
    *,
    session: Session,
    job: Job,
    media: MediaAsset,
    transcript_payload: dict[str, Any] | None,
    media_inspection_payload: dict[str, Any] | None,
    manifest_doc: dict[str, Any],
    out_bucket: str,
    settings: Any,
) -> str | None:
    """When ``FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED`` is true, write ``agent_bundle.json`` and register output.

    Runs **before** processing-minute settlement. On failure raises ``JobProcessingFailure`` so the job
    fails without debiting reserved minutes (same as other pipeline failures).

    Returns the **outputs** storage key for ``agent_bundle.json`` after a successful upload, else ``None``.
    """
    if not feedfoundry_agent_bundle_enabled():
        return None
    if not transcript_payload:
        log.info("agent_bundle_skipped job_id=%s reason=no_transcript", job.id)
        return None
    segs = transcript_payload.get("segments") or []
    if not segs:
        log.info("agent_bundle_skipped job_id=%s reason=no_transcript_segments", job.id)
        return None

    job_input = build_feedfoundry_job_input_from_worker(
        job=job,
        media=media,
        transcript_payload=transcript_payload,
        media_inspection_payload=media_inspection_payload,
    )
    try:
        bundle = run_feedfoundry_agent_bundle(job_input)
        body = bundle.model_dump_json(indent=2).encode("utf-8")
    except Exception as exc:
        log.error(
            "agent_bundle_failed job_id=%s error=%s",
            job.id,
            json.dumps({"error_type": type(exc).__name__, "error": str(exc)[:2000]}),
        )
        raise JobProcessingFailure(
            "agent_bundle_failed",
            "FeedFoundry agent bundle step failed; job was not charged for this work.",
        ) from exc

    org_id = job.organisation_id
    filename = "agent_bundle.json"
    key = job_output_object_key(org_id=org_id, job_id=job.id, filename=filename)
    put_json_bytes(bucket=out_bucket, key=key, body=body, settings=settings)
    manifest_doc["outputs"].append(
        {"output_type": JobOutputType.AGENT_BUNDLE.value, "storage_key": key, "filename": filename}
    )
    session.add(
        JobOutput(
            job_id=job.id,
            organisation_id=org_id,
            output_type=JobOutputType.AGENT_BUNDLE,
            schema_version="1.0",
            storage_key=key,
            json_payload=None,
        )
    )
    log.info("agent_bundle_written job_id=%s storage_key=%s", job.id, key)
    return key
