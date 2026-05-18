from __future__ import annotations

from app.models import YoutubeSourceQueue


def test_admin_youtube_queue_exposes_acquisition_fields(api_client, db_session) -> None:
    row = YoutubeSourceQueue(
        id="ytq_admin_fields",
        organisation_id="org_admin_fields",
        youtube_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        status="queued",
        queue_kind="video",
        media_asset_id="ma_admin_fields",
        job_id="job_admin_fields",
        acquisition_status="acquisition_succeeded",
        acquisition_error=None,
        temp_media_storage_key="orgs/org_admin_fields/assets/ma_admin_fields/source/youtube_source.mp4",
        source_title="Me at the zoo",
        source_duration_seconds=19.0,
    )
    db_session.add(row)
    db_session.commit()

    resp = api_client.get(
        "/v1/admin/youtube-queue?limit=5",
        headers={"Authorization": "Bearer test-internal-key"},
    )

    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == "ytq_admin_fields")
    assert item["queue_kind"] == "video"
    assert item["media_asset_id"] == "ma_admin_fields"
    assert item["job_id"] == "job_admin_fields"
    assert item["acquisition_status"] == "acquisition_succeeded"
    assert item["acquisition_error"] is None
    assert item["temp_media_storage_key"].endswith("/youtube_source.mp4")
    assert item["source_title"] == "Me at the zoo"
    assert item["source_duration_seconds"] == 19.0
