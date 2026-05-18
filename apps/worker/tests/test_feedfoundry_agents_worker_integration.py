"""Worker integration for FeedFoundry agent bundle (feature-flagged)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ai.feedfoundry_agents import integration as bundle_integration
from app.models import Job, JobOutputType, JobStatus, MediaAsset, MediaAssetStatus, MediaType
from pipeline.errors import JobProcessingFailure


def _job_and_media() -> tuple[Job, MediaAsset]:
    job = Job(
        id="job_agent_int",
        organisation_id="org_agent_int",
        media_asset_id="ma_agent_int",
        status=JobStatus.PROCESSING,
    )
    media = MediaAsset(
        id="ma_agent_int",
        organisation_id="org_agent_int",
        original_filename="demo_episode.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="orgs/org_agent_int/assets/ma/source/demo_episode.mp4",
        status=MediaAssetStatus.UPLOADED,
        creator_slug="demo-creator",
        asset_slug="episode-001",
    )
    return job, media


def test_feedfoundry_agent_bundle_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(bundle_integration.ENV_FLAG, raising=False)
    assert bundle_integration.feedfoundry_agent_bundle_enabled() is False


def test_feedfoundry_agent_bundle_flag_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    assert bundle_integration.feedfoundry_agent_bundle_enabled() is True


def test_build_feedfoundry_job_input_from_worker_maps_segments_and_chunks() -> None:
    job, media = _job_and_media()
    transcript = {
        "schema_version": "1.0",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
    }
    inspection = {
        "duration_seconds": 60.0,
        "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
        "chunk_plan": [{"index": 0, "start_sec": 0.0, "end_sec": 30.0}],
    }
    inp = bundle_integration.build_feedfoundry_job_input_from_worker(
        job=job,
        media=media,
        transcript_payload=transcript,
        media_inspection_payload=inspection,
    )
    assert inp.job_id == job.id
    assert len(inp.transcript.segments) == 1
    assert inp.transcript.segments[0].text == "Hello"
    assert len(inp.visual_frames) >= 1
    assert inp.media_meta.duration_seconds == 60.0
    assert inp.media_meta.container_format == "mov"


def test_maybe_write_agent_bundle_skips_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(bundle_integration.ENV_FLAG, raising=False)
    called: list[str] = []

    def _boom(_inp):
        called.append("run")
        raise AssertionError("should not run")

    monkeypatch.setattr(bundle_integration, "run_feedfoundry_agent_bundle", _boom)
    job, media = _job_and_media()
    ret = bundle_integration.maybe_write_agent_bundle(
        session=MagicMock(),
        job=job,
        media=media,
        transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
        media_inspection_payload=None,
        manifest_doc={"outputs": []},
        out_bucket="b",
        settings=MagicMock(),
    )
    assert ret is None
    assert called == []


def test_maybe_write_agent_bundle_calls_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    captured: list[str] = []

    def _capture(inp):
        captured.append(inp.job_id)
        from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle as real

        return real(inp)

    monkeypatch.setattr(bundle_integration, "run_feedfoundry_agent_bundle", _capture)
    uploaded: list[tuple[str, bytes]] = []

    def _put(*, bucket, key, body, settings):
        uploaded.append((key, body))

    monkeypatch.setattr(bundle_integration, "put_json_bytes", _put)
    session = MagicMock()
    job, media = _job_and_media()
    manifest: dict = {"outputs": []}
    key = bundle_integration.maybe_write_agent_bundle(
        session=session,
        job=job,
        media=media,
        transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
        media_inspection_payload={"duration_seconds": 10, "chunk_plan": []},
        manifest_doc=manifest,
        out_bucket="bucket",
        settings=MagicMock(),
    )
    assert key is not None
    assert key.endswith("/agent_bundle.json")
    assert captured == [job.id]
    assert len(uploaded) == 1
    assert uploaded[0][0].endswith("/agent_bundle.json")
    session.add.assert_called_once()
    add_kw = session.add.call_args[0][0]
    assert add_kw.output_type == JobOutputType.AGENT_BUNDLE
    assert any(o.get("filename") == "agent_bundle.json" for o in manifest["outputs"])


def test_maybe_write_agent_bundle_flag_off_writes_no_visual_evidence_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    monkeypatch.delenv("FF_WORKER_VISUAL_EVIDENCE_ENABLED", raising=False)
    uploaded: list[tuple[str, bytes]] = []

    def _put(*, bucket, key, body, settings):
        uploaded.append((key, body))

    monkeypatch.setattr(bundle_integration, "put_json_bytes", _put)
    job, media = _job_and_media()
    manifest: dict = {"outputs": []}

    key = bundle_integration.maybe_write_agent_bundle(
        session=MagicMock(),
        job=job,
        media=media,
        transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
        media_inspection_payload={"duration_seconds": 10, "chunk_plan": []},
        manifest_doc=manifest,
        out_bucket="bucket",
        settings=MagicMock(),
    )

    assert key and key.endswith("/agent_bundle.json")
    assert [k for k, _body in uploaded if k.endswith("/visual_evidence.json")] == []
    assert not any(o.get("filename") == "visual_evidence.json" for o in manifest["outputs"])


def test_maybe_write_agent_bundle_flag_on_persists_visual_evidence_and_bundle_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    monkeypatch.setenv("FF_WORKER_VISUAL_EVIDENCE_ENABLED", "1")
    uploaded: list[tuple[str, bytes]] = []

    def _put(*, bucket, key, body, settings):
        uploaded.append((key, body))

    monkeypatch.setattr(bundle_integration, "put_json_bytes", _put)
    job, media = _job_and_media()
    manifest: dict = {"outputs": []}

    key = bundle_integration.maybe_write_agent_bundle(
        session=MagicMock(),
        job=job,
        media=media,
        transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
        media_inspection_payload={"duration_seconds": 10, "chunk_plan": [{"index": 1, "start_sec": 0}]},
        manifest_doc=manifest,
        out_bucket="bucket",
        settings=MagicMock(),
    )

    visual_key = next(k for k, _body in uploaded if k.endswith("/visual_evidence.json"))
    bundle_body = next(body for k, body in uploaded if k.endswith("/agent_bundle.json"))
    bundle = json.loads(bundle_body.decode("utf-8"))

    assert key and key.endswith("/agent_bundle.json")
    assert bundle["visual_evidence"]["visual_evidence_package_uri"] == visual_key
    assert bundle["hosted_manifest_hints"]["visual_evidence_package_uri"] == visual_key
    assert bundle["repository_manifest"]["visual_evidence_package_uri"] == visual_key
    assert bundle["geo_freshness"]["visual_evidence_package_uri"] == visual_key
    assert any(o.get("filename") == "visual_evidence.json" and o.get("storage_key") == visual_key for o in manifest["outputs"])


def test_visual_evidence_artifact_write_failure_gates_bundle_without_fake_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    monkeypatch.setenv("FF_WORKER_VISUAL_EVIDENCE_ENABLED", "1")
    uploaded: list[tuple[str, bytes]] = []

    def _put(*, bucket, key, body, settings):
        if key.endswith("/visual_evidence.json"):
            raise OSError("simulated visual evidence write failure")
        uploaded.append((key, body))

    monkeypatch.setattr(bundle_integration, "put_json_bytes", _put)
    job, media = _job_and_media()
    manifest: dict = {"outputs": []}

    bundle_integration.maybe_write_agent_bundle(
        session=MagicMock(),
        job=job,
        media=media,
        transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
        media_inspection_payload={"duration_seconds": 10, "chunk_plan": [{"index": 1, "start_sec": 0}]},
        manifest_doc=manifest,
        out_bucket="bucket",
        settings=MagicMock(),
    )
    bundle_body = next(body for k, body in uploaded if k.endswith("/agent_bundle.json"))
    bundle = json.loads(bundle_body.decode("utf-8"))

    assert bundle["visual_evidence"]["evidence_status"] in {"needs_review", "artifact_write_failed"}
    assert bundle["visual_evidence"]["visual_evidence_package_uri"] is None
    assert bundle["hosted_manifest_hints"]["visual_evidence_package_uri"] is None
    assert not any(o.get("filename") == "visual_evidence.json" for o in manifest["outputs"])


def test_maybe_write_agent_bundle_failure_raises_job_processing_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bundle_integration.ENV_FLAG, "1")
    monkeypatch.setattr(bundle_integration, "run_feedfoundry_agent_bundle", lambda _inp: (_ for _ in ()).throw(RuntimeError("simulated bundle fault")))
    job, media = _job_and_media()
    with pytest.raises(JobProcessingFailure) as ei:
        bundle_integration.maybe_write_agent_bundle(
            session=MagicMock(),
            job=job,
            media=media,
            transcript_payload={"segments": [{"start": 0, "end": 1, "text": "x"}]},
            media_inspection_payload=None,
            manifest_doc={"outputs": []},
            out_bucket="b",
            settings=MagicMock(),
        )
    assert ei.value.code == "agent_bundle_failed"


def test_worker_orders_settlement_after_write_stub_outputs() -> None:
    """Contract: processing minutes are debited only after ``_write_stub_outputs`` returns (success path)."""
    import inspect

    import worker as worker_mod

    src = inspect.getsource(worker_mod.process_job)
    assert src.index("_write_stub_outputs") < src.index("_settle_processing_allowance")
