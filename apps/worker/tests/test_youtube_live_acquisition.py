from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus, MediaType, Organisation, YoutubeSourceQueue


def _engine():
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["FF_INTERNAL_API_KEY"] = "test-worker-youtube-key"
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_youtube_job(session: Session, *, qid: str = "ytq_live", job_id: str = "job_live", ma_id: str = "ma_live"):
    org_id = "org_live"
    session.add(Organisation(id=org_id, name="Live Org", slug="live-org"))
    media = MediaAsset(
        id=ma_id,
        organisation_id=org_id,
        original_filename="youtube_source.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key=f"ff-youtube-pending:{qid}",
        intake_kind="youtube_stub",
        status=MediaAssetStatus.UPLOADED,
    )
    job = Job(
        id=job_id,
        organisation_id=org_id,
        media_asset_id=ma_id,
        status=JobStatus.PROCESSING,
        estimated_processing_minutes=25,
        reserved_processing_minutes=25,
    )
    queue = YoutubeSourceQueue(
        id=qid,
        organisation_id=org_id,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status="queued",
        queue_kind="video",
        job_id=job_id,
        media_asset_id=ma_id,
        acquisition_status="queued_for_worker",
    )
    session.add(media)
    session.add(job)
    session.add(queue)
    session.commit()
    return job, media, queue


def test_stage_live_youtube_source_success_uploads_media_and_marks_queue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import worker as worker_mod
    from youtube_acquisition import YouTubeAcquisitionResult

    engine = _engine()
    local_media = tmp_path / "source.mp4"
    local_media.write_bytes(b"fake mp4 bytes")
    uploads: list[tuple[str, str, str]] = []

    def fake_acquire(*, youtube_url: str, work_dir: str):
        assert youtube_url.endswith("dQw4w9WgXcQ")
        assert Path(work_dir).exists()
        return YouTubeAcquisitionResult(
            local_media_path=str(local_media),
            filename="downloaded.mp4",
            content_type="video/mp4",
            title="Demo title",
            duration_seconds=12.5,
            transcript_payload={"schema_version": "1.0", "source": "youtube_transcript", "segments": [{"start": 0, "end": 1, "text": "hello"}]},
        )

    monkeypatch.setattr(worker_mod, "acquire_youtube_source", fake_acquire)

    def fake_upload(*, bucket, key, local_path, content_type, settings):
        uploads.append((bucket, key, Path(local_path).read_text()))

    monkeypatch.setattr(worker_mod, "_upload_file_to_source_storage", fake_upload)

    with Session(engine) as session:
        job, media, _queue = _seed_youtube_job(session)
        result = worker_mod._stage_live_youtube_source(session, job, media, settings=MagicMock(), src_bucket="source-bucket")
        session.refresh(media)
        row = session.get(YoutubeSourceQueue, "ytq_live")

    assert result.transcript_payload["source"] == "youtube_transcript"
    assert media.storage_source_key.endswith("/downloaded.mp4")
    assert media.intake_kind == "youtube_live"
    assert media.duration_seconds == 12.5
    assert row.acquisition_status == "acquisition_succeeded"
    assert row.acquisition_error is None
    assert row.source_title == "Demo title"
    assert row.temp_media_storage_key == media.storage_source_key
    assert uploads == [("source-bucket", media.storage_source_key, "fake mp4 bytes")]


def test_stage_live_youtube_source_failure_marks_queue_failed(monkeypatch: pytest.MonkeyPatch):
    import worker as worker_mod
    from pipeline.errors import JobProcessingFailure
    from youtube_acquisition import YouTubeAcquisitionError

    engine = _engine()

    def fake_acquire(*, youtube_url: str, work_dir: str):
        raise YouTubeAcquisitionError("yt_dlp_missing", "yt-dlp dependency is not installed")

    monkeypatch.setattr(worker_mod, "acquire_youtube_source", fake_acquire)

    with Session(engine) as session:
        job, media, _queue = _seed_youtube_job(session)
        with pytest.raises(JobProcessingFailure) as exc:
            worker_mod._stage_live_youtube_source(session, job, media, settings=MagicMock(), src_bucket="source-bucket")
        row = session.get(YoutubeSourceQueue, "ytq_live")

    assert exc.value.code == "youtube_acquisition_failed"
    assert row.acquisition_status == "acquisition_failed"
    assert "yt-dlp dependency" in row.acquisition_error


def test_stage_live_youtube_source_transcript_only_marks_partial_success(monkeypatch: pytest.MonkeyPatch):
    import worker as worker_mod
    from youtube_acquisition import YouTubeAcquisitionResult

    engine = _engine()
    uploads: list[tuple[str, str]] = []

    transcript = {
        "schema_version": "1.0",
        "source": "youtube_transcript",
        "segments": [{"start": 0, "end": 1, "text": "caption only"}],
    }

    def fake_acquire(*, youtube_url: str, work_dir: str):
        return YouTubeAcquisitionResult(
            local_media_path=None,
            filename="youtube_transcript.json",
            content_type="application/json",
            title="Caption-only title",
            duration_seconds=None,
            transcript_payload=transcript,
            media_acquired=False,
            nonfatal_error="yt-dlp bot check; public captions acquired",
        )

    monkeypatch.setattr(worker_mod, "acquire_youtube_source", fake_acquire)
    monkeypatch.setattr(worker_mod, "_upload_file_to_source_storage", lambda **kwargs: uploads.append((kwargs["bucket"], kwargs["key"])))

    with Session(engine) as session:
        job, media, _queue = _seed_youtube_job(session)
        result = worker_mod._stage_live_youtube_source(session, job, media, settings=MagicMock(), src_bucket="source-bucket")
        session.refresh(media)
        row = session.get(YoutubeSourceQueue, "ytq_live")

    assert result.transcript_payload == transcript
    assert result.media_acquired is False
    assert uploads == []
    assert media.storage_source_key == "ff-youtube-pending:ytq_live"
    assert media.intake_kind == "youtube_transcript_only"
    assert media.original_filename == "youtube_transcript.json"
    assert row.acquisition_status == "acquisition_succeeded"
    assert row.temp_media_storage_key is None
    assert "public captions acquired" in row.acquisition_error


def test_process_job_live_flag_calls_acquisition_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import worker as worker_mod
    from youtube_acquisition import YouTubeAcquisitionResult

    engine = _engine()
    calls: list[str] = []
    downloaded = tmp_path / "downloaded.mp4"
    downloaded.write_bytes(b"video")
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"wav")

    def fake_stage(session, job, media, *, settings, src_bucket):
        calls.append(job.id)
        media.storage_source_key = f"orgs/{job.organisation_id}/assets/{media.id}/source/downloaded.mp4"
        media.intake_kind = "youtube_live"
        session.add(media)
        session.commit()
        return YouTubeAcquisitionResult(
            local_media_path=str(downloaded),
            filename="downloaded.mp4",
            transcript_payload={"schema_version": "1.0", "source": "youtube_transcript", "segments": [{"start": 0, "end": 1, "text": "hello"}]},
        )

    monkeypatch.setenv("FF_YOUTUBE_SOURCE_ACQUISITION_LIVE", "1")
    monkeypatch.setattr(worker_mod, "_stage_live_youtube_source", fake_stage)
    monkeypatch.setattr(worker_mod, "_s3_client", lambda settings: object())
    monkeypatch.setattr(worker_mod, "bucket_for_source", lambda settings: "source-bucket")
    monkeypatch.setattr(worker_mod, "_wait_for_source_object", lambda **kwargs: True)
    monkeypatch.setattr(worker_mod, "download_object_to_tempfile", lambda **kwargs: str(downloaded))
    monkeypatch.setattr(worker_mod, "inspect_media_file", lambda *args, **kwargs: {"duration_seconds": 1, "chunk_plan": []})
    monkeypatch.setattr(worker_mod, "run_audio_extraction", lambda **kwargs: (str(wav), {"success": True, "source_duration_seconds": 1}))
    monkeypatch.setattr(worker_mod, "run_transcript_pipeline_v0", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should use acquired transcript")))
    monkeypatch.setattr(worker_mod, "_write_stub_outputs", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker_mod, "_settle_processing_allowance", lambda *args, **kwargs: None)

    with Session(engine) as session:
        job, _media, _queue = _seed_youtube_job(session)
        worker_mod.process_job(session, job)
        session.refresh(job)

    assert calls == ["job_live"]
    assert job.status == JobStatus.COMPLETED


def test_stage_live_youtube_source_requires_pending_queue():
    import worker as worker_mod

    engine = _engine()
    with Session(engine) as session:
        session.add(Organisation(id="org_noq", name="NoQ", slug="noq"))
        media = MediaAsset(
            id="ma_noq",
            organisation_id="org_noq",
            original_filename="youtube_source.mp4",
            media_type=MediaType.VIDEO,
            storage_source_key="ff-youtube-pending:missing",
            intake_kind="youtube_stub",
            status=MediaAssetStatus.UPLOADED,
        )
        job = Job(id="job_noq", organisation_id="org_noq", media_asset_id="ma_noq", status=JobStatus.PROCESSING)
        session.add(media)
        session.add(job)
        session.commit()
        with pytest.raises(Exception) as exc:
            worker_mod._stage_live_youtube_source(session, job, media, settings=MagicMock(), src_bucket="source-bucket")

    assert "youtube_source_queue" in str(exc.value)
