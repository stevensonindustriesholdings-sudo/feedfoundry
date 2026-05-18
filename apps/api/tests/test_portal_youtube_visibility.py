from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models import (
    AnnualAccess,
    CreditWallet,
    Job,
    JobOutput,
    JobOutputType,
    JobStatus,
    MediaAsset,
    MediaType,
    Organisation,
    User,
    YoutubeSourceQueue,
    utcnow,
)


def _bootstrap_org(session: Session, org_id: str) -> None:
    session.add(Organisation(id=org_id, name="Portal Org", slug=f"slug-{org_id}"))
    session.add(User(id=f"user_{org_id}", organisation_id=org_id, email=f"{org_id}@example.com"))
    now = utcnow()
    session.add(
        AnnualAccess(
            organisation_id=org_id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_processing_minutes_annual=500,
        )
    )
    session.add(CreditWallet(organisation_id=org_id, processing_minutes_available=500))
    session.commit()


def test_org_youtube_queue_exposes_source_title_duration_and_acquisition_failure(api_client, db_session: Session) -> None:
    org_id = "org_portal_yt"
    _bootstrap_org(db_session, org_id)
    row = YoutubeSourceQueue(
        id="ytq_portal_blocked",
        organisation_id=org_id,
        youtube_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        status="failed",
        queue_kind="video",
        acquisition_status="blocked_by_youtube",
        acquisition_error="YouTube returned a bot-verification page before media acquisition.",
        source_title="Me at the zoo",
        source_duration_seconds=19.0,
    )
    db_session.add(row)
    db_session.commit()

    resp = api_client.get(
        "/v1/youtube-source-queue?limit=5",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
    )

    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["items"] if i["id"] == "ytq_portal_blocked")
    assert item["source_title"] == "Me at the zoo"
    assert item["source_duration_seconds"] == 19.0
    assert item["acquisition_status"] == "blocked_by_youtube"
    assert item["acquisition_error"] == "YouTube returned a bot-verification page before media acquisition."


def test_job_list_exposes_completed_youtube_source_and_output_presence(api_client, db_session: Session) -> None:
    org_id = "org_portal_completed"
    _bootstrap_org(db_session, org_id)
    media = MediaAsset(
        id="ma_portal_completed",
        organisation_id=org_id,
        original_filename="youtube-source.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="orgs/org_portal_completed/assets/ma_portal_completed/source/youtube_source.mp4",
        intake_kind="youtube",
        duration_seconds=19.0,
    )
    job = Job(
        id="job_portal_completed",
        organisation_id=org_id,
        media_asset_id=media.id,
        media_kind=MediaType.VIDEO,
        status=JobStatus.COMPLETED,
        progress_percent=100,
        current_stage="completed",
    )
    queue = YoutubeSourceQueue(
        id="ytq_portal_completed",
        organisation_id=org_id,
        youtube_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        status="completed",
        queue_kind="video",
        media_asset_id=media.id,
        job_id=job.id,
        acquisition_status="acquisition_succeeded",
        source_title="Me at the zoo",
        source_duration_seconds=19.0,
    )
    db_session.add(media)
    db_session.add(job)
    db_session.add(queue)
    for output_type in (
        JobOutputType.RAW_TRANSCRIPT,
        JobOutputType.HOSTED_MANIFEST,
        JobOutputType.AGENT_BUNDLE,
        JobOutputType.EXPORT_BUNDLE,
    ):
        payload = {"type": output_type.value}
        if output_type == JobOutputType.HOSTED_MANIFEST:
            payload["artifacts"] = {
                "visual_evidence": {
                    "filename": "visual_evidence.json",
                    "storage_key": f"orgs/{org_id}/jobs/{job.id}/outputs/visual_evidence.json",
                }
            }
        db_session.add(
            JobOutput(
                job_id=job.id,
                organisation_id=org_id,
                output_type=output_type,
                json_payload=payload,
                storage_key=f"orgs/{org_id}/jobs/{job.id}/outputs/{output_type.value}.json",
            )
        )
    db_session.commit()

    resp = api_client.get(
        "/v1/jobs?limit=5",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
    )

    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["jobs"] if i["job_id"] == job.id)
    assert item["source_kind"] == "youtube"
    assert item["source_title"] == "Me at the zoo"
    assert item["source_duration_seconds"] == 19.0
    assert item["acquisition_status"] == "acquisition_succeeded"
    assert item["acquisition_error"] is None
    assert item["has_transcript"] is True
    assert item["has_hosted_manifest"] is True
    assert item["has_agent_bundle"] is True
    assert item["has_export_bundle"] is True
    assert item["has_visual_evidence"] is True


def test_job_list_marks_agent_bundle_absent_when_no_output(api_client, db_session: Session) -> None:
    org_id = "org_portal_no_agent"
    _bootstrap_org(db_session, org_id)
    media = MediaAsset(
        id="ma_portal_no_agent",
        organisation_id=org_id,
        original_filename="upload.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="orgs/org_portal_no_agent/assets/ma_portal_no_agent/source/upload.mp4",
        intake_kind="upload",
        duration_seconds=42.0,
    )
    job = Job(
        id="job_portal_no_agent",
        organisation_id=org_id,
        media_asset_id=media.id,
        media_kind=MediaType.VIDEO,
        status=JobStatus.COMPLETED,
        progress_percent=100,
        current_stage="completed",
    )
    db_session.add(media)
    db_session.add(job)
    db_session.add(
        JobOutput(
            job_id=job.id,
            organisation_id=org_id,
            output_type=JobOutputType.RAW_TRANSCRIPT,
            json_payload={"text": "hello"},
            storage_key=f"orgs/{org_id}/jobs/{job.id}/outputs/raw_transcript.json",
        )
    )
    db_session.commit()

    resp = api_client.get(
        "/v1/jobs?limit=5",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
    )

    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["jobs"] if i["job_id"] == job.id)
    assert item["source_kind"] == "upload"
    assert item["source_duration_seconds"] == 42.0
    assert item["has_transcript"] is True
    assert item["has_hosted_manifest"] is False
    assert item["has_agent_bundle"] is False
    assert item["has_export_bundle"] is False
    assert item["has_visual_evidence"] is False


def test_job_status_exposes_failure_reason_for_portal(api_client, db_session: Session) -> None:
    org_id = "org_portal_job_failure"
    _bootstrap_org(db_session, org_id)
    media = MediaAsset(
        id="ma_portal_failed",
        organisation_id=org_id,
        original_filename="youtube-source.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="ff-youtube-pending:ytq_failed",
        intake_kind="youtube_stub",
    )
    job = Job(
        id="job_portal_failed",
        organisation_id=org_id,
        media_asset_id=media.id,
        media_kind=MediaType.VIDEO,
        status=JobStatus.FAILED,
        progress_percent=100,
        current_stage="source_acquisition",
        failure_code="youtube_blocked",
        failure_reason="youtube_blocked",
        failure_message="YouTube blocked source acquisition for this URL.",
    )
    db_session.add(media)
    db_session.add(job)
    db_session.commit()

    resp = api_client.get(
        "/v1/jobs/job_portal_failed",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org_id},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["failure_code"] == "youtube_blocked"
    assert body["failure_reason"] == "youtube_blocked"
    assert body["failure_message"] == "YouTube blocked source acquisition for this URL."
