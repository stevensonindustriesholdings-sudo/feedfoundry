from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.config.env_validation import validate_worker_environment  # noqa: E402
from app.models import (  # noqa: E402
    Job,
    JobOutput,
    JobOutputType,
    JobStatus,
    MediaAsset,
    WorkerHeartbeat,
    utcnow,
)
from app.services.credit_ledger import (  # noqa: E402
    debit_reserved_credits,
    ledger_debit_key,
    ledger_goodwill_revoke_key,
    ledger_release_failure_key,
    ledger_release_remainder_key,
    release_reserved_credits,
    revoke_goodwill_processing_minutes_on_job_failure,
)
from app.services.storage import (  # noqa: E402
    _s3_client,
    bucket_for_outputs,
    bucket_for_source,
    download_object_to_tempfile,
    head_object_exists,
    job_manifest_object_key,
    job_output_object_key,
    put_json_bytes,
)
from app.settings import get_settings  # noqa: E402

from media_inspection import inspect_media_file  # noqa: E402
from pipeline.audio_extraction import run_audio_extraction  # noqa: E402
from pipeline.transcript import TranscriptPipelineInput, run_transcript_pipeline_v0  # noqa: E402
from pipeline.transcript_derived_outputs import (  # noqa: E402
    build_chapters_from_transcript,
    build_fact_sheet_from_transcript,
    build_faqs_from_transcript,
    build_hosted_manifest_from_transcript,
    build_metadata_from_transcript,
    derived_from_for_transcript,
)  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("feedfoundry.worker")

# Stub artefacts (deterministic JSON). Filenames match vertical-slice contract.
STUB_OUTPUT_SPECS: list[tuple[str, JobOutputType, dict]] = [
    (
        "transcript.json",
        JobOutputType.RAW_TRANSCRIPT,
        {
            "schema_version": "1.0",
            "segments": [{"start": 0.0, "end": 1.0, "text": "stub transcript"}],
        },
    ),
    (
        "chapters.json",
        JobOutputType.CHAPTERS,
        {"schema_version": "1.0", "chapters": [{"title": "Intro", "start_seconds": 0.0}]},
    ),
    (
        "factsheet.json",
        JobOutputType.FACT_SHEET,
        {"schema_version": "1.0", "facts": [{"statement": "Stub fact"}]},
    ),
    (
        "faq.json",
        JobOutputType.FAQS,
        {"schema_version": "1.0", "faqs": [{"question": "Stub?", "answer": "Stub."}]},
    ),
    (
        "metadata.json",
        JobOutputType.METADATA,
        {
            "schema_version": "1.0",
            "youtube": {"title": "Stub episode"},
            "podcast": {"title": "Stub episode"},
        },
    ),
    (
        "hosted_manifest.json",
        JobOutputType.HOSTED_MANIFEST,
        {
            "schema_version": "1.0",
            "creator_slug": "demo-creator",
            "asset_slug": "episode-001",
            "canonical_title": "Stub Episode",
            "summary": "Stub summary.",
            "chapters": [],
            "topics": [],
            "facts": [],
            "faqs": [],
            "ctas": [],
            "links": {},
        },
    ),
]

STUB_TEMPLATE_BY_TYPE: dict[JobOutputType, dict] = {ot: dict(payload) for _fn, ot, payload in STUB_OUTPUT_SPECS}
OUTPUT_WRITE_ORDER: list[tuple[str, JobOutputType]] = [(fn, ot) for fn, ot, _p in STUB_OUTPUT_SPECS]


def _claim_job_sqlite(session: Session):
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at)  # type: ignore[arg-type]
        .limit(1)
        .with_for_update()
    )
    return session.exec(stmt).first()


def _claim_job_postgres(session: Session):
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at)  # type: ignore[arg-type]
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.exec(stmt).first()


def claim_next_job(session: Session) -> Job | None:
    dialect = session.get_bind().dialect.name
    job = _claim_job_postgres(session) if dialect == "postgresql" else _claim_job_sqlite(session)
    if not job:
        return None
    job.status = JobStatus.PROBING
    job.current_stage = "Claimed job"
    job.progress_percent = 5
    if job.started_at is None:
        job.started_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _advance(session: Session, job: Job, status: JobStatus, stage: str, progress: int) -> None:
    job.status = status
    job.current_stage = stage
    job.progress_percent = progress
    session.add(job)
    session.commit()


def _write_stub_outputs(
    session: Session,
    job: Job,
    media: MediaAsset,
    *,
    media_inspection_payload: dict | None = None,
    transcript_payload: dict | None = None,
) -> None:
    settings = get_settings()
    out_bucket = bucket_for_outputs(settings)
    org_id = job.organisation_id

    prior = session.exec(select(JobOutput).where(JobOutput.job_id == job.id)).all()
    for row in prior:
        session.delete(row)
    session.commit()

    manifest_doc = {
        "schema_version": "1.0",
        "job_id": job.id,
        "organisation_id": org_id,
        "media_asset_id": media.id,
        "outputs": [],
    }

    include_mi = media_inspection_payload is not None
    planned_types = [
        JobOutputType.RAW_TRANSCRIPT.value,
        JobOutputType.CHAPTERS.value,
        JobOutputType.FACT_SHEET.value,
        JobOutputType.FAQS.value,
        JobOutputType.METADATA.value,
        JobOutputType.HOSTED_MANIFEST.value,
    ]
    if include_mi:
        planned_types.append(JobOutputType.MEDIA_INSPECTION.value)

    for filename, output_type in OUTPUT_WRITE_ORDER:
        if output_type == JobOutputType.RAW_TRANSCRIPT and transcript_payload is not None:
            payload = dict(transcript_payload)
        elif output_type == JobOutputType.RAW_TRANSCRIPT:
            payload = dict(STUB_TEMPLATE_BY_TYPE[JobOutputType.RAW_TRANSCRIPT])
        elif transcript_payload is not None:
            df = derived_from_for_transcript(transcript_payload)
            if output_type == JobOutputType.CHAPTERS:
                payload = build_chapters_from_transcript(
                    transcript_payload, media_inspection_payload, derived_from=df
                )
            elif output_type == JobOutputType.FACT_SHEET:
                payload = build_fact_sheet_from_transcript(
                    transcript_payload, media_inspection_payload, derived_from=df
                )
            elif output_type == JobOutputType.FAQS:
                payload = build_faqs_from_transcript(
                    transcript_payload, media_inspection_payload, derived_from=df
                )
            elif output_type == JobOutputType.METADATA:
                payload = build_metadata_from_transcript(
                    transcript_payload,
                    media_inspection_payload,
                    derived_from=df,
                    original_basename=media.original_filename,
                )
            elif output_type == JobOutputType.HOSTED_MANIFEST:
                payload = build_hosted_manifest_from_transcript(
                    transcript=transcript_payload,
                    media_inspection=media_inspection_payload,
                    creator_slug=media.creator_slug or "",
                    asset_slug=media.asset_slug or "",
                    original_basename=media.original_filename,
                    outputs_available=planned_types,
                    derived_from=df,
                )
            else:
                payload = dict(STUB_TEMPLATE_BY_TYPE[output_type])
        else:
            payload = dict(STUB_TEMPLATE_BY_TYPE[output_type])
        if output_type == JobOutputType.HOSTED_MANIFEST and transcript_payload is None:
            if media.creator_slug:
                payload["creator_slug"] = media.creator_slug
            if media.asset_slug:
                payload["asset_slug"] = media.asset_slug

        key = job_output_object_key(org_id=org_id, job_id=job.id, filename=filename)
        body = json.dumps(payload, indent=2).encode("utf-8")
        put_json_bytes(bucket=out_bucket, key=key, body=body, settings=settings)
        manifest_doc["outputs"].append(
            {"output_type": output_type.value, "storage_key": key, "filename": filename}
        )

        jo = JobOutput(
            job_id=job.id,
            organisation_id=org_id,
            output_type=output_type,
            storage_key=key,
            json_payload=payload if output_type == JobOutputType.HOSTED_MANIFEST else None,
        )
        session.add(jo)

    if media_inspection_payload is not None:
        filename = "media_inspection.json"
        key = job_output_object_key(org_id=org_id, job_id=job.id, filename=filename)
        body = json.dumps(media_inspection_payload, indent=2).encode("utf-8")
        put_json_bytes(bucket=out_bucket, key=key, body=body, settings=settings)
        manifest_doc["outputs"].append(
            {"output_type": JobOutputType.MEDIA_INSPECTION.value, "storage_key": key, "filename": filename}
        )
        session.add(
            JobOutput(
                job_id=job.id,
                organisation_id=org_id,
                output_type=JobOutputType.MEDIA_INSPECTION,
                storage_key=key,
                json_payload=None,
            )
        )

    if media.creator_slug:
        manifest_doc["creator_slug"] = media.creator_slug
    if media.asset_slug:
        manifest_doc["asset_slug"] = media.asset_slug

    mkey = job_manifest_object_key(org_id=org_id, job_id=job.id)
    put_json_bytes(
        bucket=out_bucket,
        key=mkey,
        body=json.dumps(manifest_doc, indent=2).encode("utf-8"),
        settings=settings,
    )
    session.commit()


def _settle_credits(session: Session, job: Job) -> None:
    reserved = int(job.reserved_credits or 0)
    estimated = int(job.estimated_credits or reserved or 0)
    actual = min(reserved, estimated) if reserved else 0

    if reserved and actual:
        debit_reserved_credits(
            session,
            organisation_id=job.organisation_id,
            job_id=job.id,
            amount=actual,
            idempotency_key=ledger_debit_key(job.id),
        )
    remainder = reserved - actual
    if remainder > 0:
        release_reserved_credits(
            session,
            organisation_id=job.organisation_id,
            job_id=job.id,
            amount=remainder,
            idempotency_key=ledger_release_remainder_key(job.id),
        )

    job.actual_credits = actual
    session.add(job)
    session.commit()


def _wait_for_source_object(
    *,
    bucket: str,
    key: str,
    settings,
    max_wait_seconds: float,
) -> bool:
    """HEAD until object exists or timeout (S3/R2 read-after-write after presigned PUT)."""
    deadline = time.monotonic() + max(0.5, max_wait_seconds)
    interval = 0.2
    while time.monotonic() < deadline:
        if head_object_exists(bucket=bucket, key=key, settings=settings):
            return True
        time.sleep(interval)
        interval = min(interval * 1.4, 2.5)
    return False


def process_job(session: Session, job: Job) -> None:
    settings = get_settings()
    media = session.get(MediaAsset, job.media_asset_id)
    if not media:
        raise RuntimeError("media_missing")

    src_bucket = bucket_for_source(settings)
    skip_verify = os.environ.get("FF_SKIP_SOURCE_VERIFY", "").lower() in ("1", "true", "yes")
    strict_source = os.environ.get("FF_STRICT_SOURCE_VERIFY", "").lower() in ("1", "true", "yes")
    app_env = (settings.app_env or "").lower()
    can_head = _s3_client(settings) is not None

    missing_source_continued = False
    source_present = True
    if not skip_verify and can_head:
        max_wait = float(os.environ.get("FF_SOURCE_HEAD_MAX_WAIT_SECONDS", "45"))
        source_present = _wait_for_source_object(
            bucket=src_bucket,
            key=media.storage_source_key,
            settings=settings,
            max_wait_seconds=max_wait,
        )
    if not skip_verify and can_head and not source_present:
        if app_env == "staging" and not strict_source:
            missing_source_continued = True
            log.warning(
                "staging_missing_source_continuing_stub job_id=%s media_asset_id=%s key=%s",
                job.id,
                media.id,
                media.storage_source_key,
            )
        else:
            raise RuntimeError("source_object_missing")
    elif not skip_verify and not can_head:
        log.warning(
            "worker_skip_source_head_no_s3_client job_id=%s app_env=%s",
            job.id,
            app_env,
        )

    _advance(session, job, JobStatus.EXTRACTING_AUDIO, "Extracting audio", 20)
    _advance(session, job, JobStatus.CHUNKING, "Chunking", 35)
    _advance(session, job, JobStatus.TRANSCRIBING, "Transcribing", 50)
    _advance(session, job, JobStatus.GENERATING_OUTPUTS, "Generating outputs", 72)
    _advance(session, job, JobStatus.QA_VALIDATING, "QA validation", 88)
    _advance(session, job, JobStatus.EXPORTING, "Writing outputs to object storage", 95)

    media_inspection_payload: dict | None = None
    transcript_payload: dict | None = None
    local_video: str | None = None
    wav_path: str | None = None
    if can_head and not missing_source_continued:
        try:
            suffix = os.path.splitext(media.original_filename or "")[1] or ".mp4"
            local_video = download_object_to_tempfile(
                bucket=src_bucket,
                key=media.storage_source_key,
                settings=settings,
                suffix=suffix,
            )
            ffprobe_bin = os.environ.get("FFPROBE_BINARY", "ffprobe")
            media_inspection_payload = inspect_media_file(local_video, ffprobe_binary=ffprobe_bin)
            wav_path, audio_meta = run_audio_extraction(
                input_path=local_video,
                ffmpeg_binary=os.environ.get("FFMPEG_BINARY"),
                ffprobe_binary=ffprobe_bin,
            )
            t_in = TranscriptPipelineInput(
                job_id=job.id,
                media_asset_id=media.id,
                audio_wav_path=wav_path,
                audio_extraction=audio_meta,
                media_inspection=media_inspection_payload,
            )
            transcript_payload = run_transcript_pipeline_v0(
                t_in,
                openai_api_key=(
                    (getattr(settings, "openai_api_key", "") or "").strip()
                    if bool(getattr(settings, "ff_ai_enabled", True))
                    else ""
                ),
            )
        except Exception as exc:
            if skip_verify:
                log.warning(
                    "skip_media_inspection_or_transcript_after_error job_id=%s err=%s",
                    job.id,
                    exc,
                )
                media_inspection_payload = None
                transcript_payload = None
            else:
                log.exception("media_inspection_or_transcript_failed job_id=%s", job.id)
                raise RuntimeError("media_inspection_or_transcript_failed") from exc
        finally:
            if local_video:
                try:
                    os.unlink(local_video)
                except OSError:
                    pass
            if wav_path:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
    elif missing_source_continued:
        log.info("skip_media_inspection_staging_missing_source job_id=%s", job.id)

    _write_stub_outputs(
        session,
        job,
        media,
        media_inspection_payload=media_inspection_payload,
        transcript_payload=transcript_payload,
    )

    _settle_credits(session, job)

    job.status = JobStatus.COMPLETE
    job.completed_at = utcnow()
    job.progress_percent = 100
    job.current_stage = "Complete"
    session.add(job)
    session.commit()


def fail_job(session: Session, job: Job, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.failure_code = code
    job.failure_message = message
    session.add(job)
    session.commit()

    amt = int(job.reserved_credits or 0)
    if amt:
        try:
            release_reserved_credits(
                session,
                organisation_id=job.organisation_id,
                job_id=job.id,
                amount=amt,
                idempotency_key=ledger_release_failure_key(job.id),
            )
            session.commit()
        except Exception:
            log.exception("ledger_failure_release")

    gw = int(job.goodwill_minutes_granted or 0)
    if gw:
        try:
            revoke_goodwill_processing_minutes_on_job_failure(
                session,
                organisation_id=job.organisation_id,
                job_id=job.id,
                minutes=gw,
                idempotency_key=ledger_goodwill_revoke_key(job.id),
            )
            session.commit()
        except Exception:
            log.exception("ledger_goodwill_revoke_failure")


_stop_event = threading.Event()


def _request_shutdown(*_args) -> None:
    log.info("worker_shutdown_requested")
    _stop_event.set()


def write_worker_heartbeat(engine, *, worker_id: str) -> None:
    s = get_settings()
    host = socket.gethostname()
    git_c = os.environ.get("GIT_COMMIT", "") or getattr(s, "git_commit", "") or ""
    build_t = os.environ.get("BUILD_TIMESTAMP", "") or getattr(s, "build_timestamp", "") or ""
    with Session(engine) as session:
        row = session.get(WorkerHeartbeat, worker_id)
        now = utcnow()
        if row:
            row.last_seen_at = now
            row.hostname = host
            row.app_env = s.app_env
            row.git_commit = git_c[:64]
            row.build_timestamp = build_t[:64]
            row.api_version = s.api_version
            session.add(row)
        else:
            session.add(
                WorkerHeartbeat(
                    worker_id=worker_id,
                    last_seen_at=now,
                    hostname=host,
                    app_env=s.app_env,
                    git_commit=git_c[:64],
                    build_timestamp=build_t[:64],
                    api_version=s.api_version,
                )
            )
        session.commit()


def _probe_database(engine) -> str:
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return f"error:{type(e).__name__}"


def main() -> None:
    settings = get_settings()
    try:
        validate_worker_environment(settings)
    except ValueError as e:
        log.error("%s", e)
        raise SystemExit(1) from e

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required")

    poll = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", str(settings.worker_poll_interval_seconds)))
    worker_id = os.environ.get("FF_WORKER_ID", "").strip() or f"{socket.gethostname()}:{os.getpid()}"

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    engine = create_engine(db_url, pool_pre_ping=True)
    db_status = _probe_database(engine)
    log.info(
        "worker_started worker_id=%s app_env=%s poll_interval_s=%s database=%s",
        worker_id,
        settings.app_env,
        poll,
        db_status,
    )

    while not _stop_event.is_set():
        try:
            with Session(engine) as session:
                job = claim_next_job(session)
                if not job:
                    write_worker_heartbeat(engine, worker_id=worker_id)
                    if _stop_event.wait(timeout=poll):
                        break
                    continue
                jid = job.id

            with Session(engine) as session:
                j = session.get(Job, jid)
                if j is None:
                    continue
                try:
                    process_job(session, j)
                except Exception as exc:
                    log.exception("job_failed job_id=%s", jid)
                    session.rollback()
                    with Session(engine) as session2:
                        j2 = session2.get(Job, jid)
                        if j2 and j2.status not in (
                            JobStatus.COMPLETE,
                            JobStatus.FAILED,
                            JobStatus.CANCELLED,
                        ):
                            fail_job(session2, j2, "processing_error", str(exc))
            write_worker_heartbeat(engine, worker_id=worker_id)
        except Exception:
            log.exception("worker_iteration_failed")
            if _stop_event.wait(timeout=poll):
                break

    log.info("worker_stopped_gracefully worker_id=%s", worker_id)


if __name__ == "__main__":
    main()
