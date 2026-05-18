"""Hosted manifest ``outputs_available`` stays aligned with persisted ``agent_bundle``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import worker as worker_mod
from app.models import JobOutputType


def test_refresh_hosted_manifest_adds_agent_bundle_when_written(monkeypatch: pytest.MonkeyPatch) -> None:
    uploaded: list[tuple[str, str]] = []

    def _put(*, bucket, key, body, settings):
        uploaded.append((bucket, key))

    monkeypatch.setattr(worker_mod, "put_json_bytes", _put)

    jo = MagicMock()
    jo.storage_key = "orgs/o1/jobs/j1/outputs/hosted_manifest.json"
    jo.json_payload = None

    session = MagicMock()

    def _exec(_stmt):
        m = MagicMock()
        m.first.return_value = jo
        return m

    session.exec.side_effect = _exec

    job = MagicMock(id="j1", organisation_id="o1")
    media = MagicMock(creator_slug="c", asset_slug="a", original_filename="clip.mp4")
    tr = {
        "schema_version": "1.0",
        "source": "transcript_stub",
        "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
    }
    planned = [
        JobOutputType.RAW_TRANSCRIPT.value,
        JobOutputType.CHAPTERS.value,
        JobOutputType.FACT_SHEET.value,
        JobOutputType.FAQS.value,
        JobOutputType.METADATA.value,
        JobOutputType.CTAS.value,
        JobOutputType.HOSTED_MANIFEST.value,
        JobOutputType.EXPORT_BUNDLE.value,
    ]
    bundle_key = "orgs/o1/jobs/j1/outputs/agent_bundle.json"

    worker_mod._refresh_hosted_manifest_for_agent_bundle(
        session=session,
        job=job,
        media=media,
        transcript_payload=tr,
        media_inspection_payload=None,
        planned_types=planned,
        agent_bundle_storage_key=bundle_key,
        out_bucket="out-bucket",
        settings=MagicMock(),
    )

    assert jo.json_payload is not None
    assert JobOutputType.AGENT_BUNDLE.value in jo.json_payload["outputs_available"]
    assert jo.json_payload["outputs_available"].index(JobOutputType.AGENT_BUNDLE.value) < jo.json_payload[
        "outputs_available"
    ].index(JobOutputType.EXPORT_BUNDLE.value)
    assert jo.json_payload.get("artifacts", {}).get("agent_bundle", {}).get("storage_key") == bundle_key
    assert uploaded and uploaded[0][1].endswith("hosted_manifest.json")


def test_refresh_hosted_manifest_skips_without_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_mod, "put_json_bytes", MagicMock())

    session = MagicMock()

    def _exec(_stmt):
        m = MagicMock()
        m.first.return_value = None
        return m

    session.exec.side_effect = _exec

    worker_mod._refresh_hosted_manifest_for_agent_bundle(
        session=session,
        job=MagicMock(id="j1"),
        media=MagicMock(creator_slug="c", asset_slug="a", original_filename="x.mp4"),
        transcript_payload={"schema_version": "1.0", "segments": [{"start": 0, "end": 1, "text": "a"}]},
        media_inspection_payload=None,
        planned_types=["raw_transcript", "export_bundle"],
        agent_bundle_storage_key="k",
        out_bucket="b",
        settings=MagicMock(),
    )
    worker_mod.put_json_bytes.assert_not_called()
