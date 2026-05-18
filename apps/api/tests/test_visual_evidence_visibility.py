from __future__ import annotations

import pytest
from sqlmodel import select

from app.models import Job, JobOutput, JobOutputType, JobStatus, MediaAsset, MediaType, Organisation
from app.services import storage as storage_service


@pytest.fixture(autouse=True)
def _storage_urls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        storage_service,
        "presign_get_for_key",
        lambda *, storage_key, download_filename=None: f"https://objects.invalid/{storage_key}",
    )


def _job_with_manifest(db_session, *, with_visual: bool = True, raw_package: bool = False):
    org = Organisation(name="Org VE", slug="visual-org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    media = MediaAsset(
        organisation_id=org.id,
        original_filename="demo.mp4",
        media_type=MediaType.VIDEO,
        storage_source_key="sk",
        creator_slug="visual-creator",
        asset_slug="visual-asset",
    )
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)

    job = Job(organisation_id=org.id, media_asset_id=media.id, status=JobStatus.COMPLETED)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    payload = {
        "schema_version": "1.0",
        "creator_slug": "visual-creator",
        "asset_slug": "visual-asset",
        "canonical_title": "Visual Asset",
        "summary": "Public summary",
        "outputs_available": ["hosted_manifest", "agent_bundle"],
        "artifacts": {
            "agent_bundle": {
                "filename": "agent_bundle.json",
                "storage_key": f"orgs/{org.id}/jobs/{job.id}/outputs/agent_bundle.json",
            }
        },
        "evidence_status": "ready" if with_visual else "needs_review",
        "visual_evidence_available": with_visual,
        "transcript_evidence_available": True,
        "unsupported_claim_count": 0 if with_visual else 2,
        "human_review_required": not with_visual,
        "final_evidence_confidence": 0.91 if with_visual else 0.42,
        "evidence_gate_reason": [] if with_visual else ["missing_visual_evidence"],
    }
    if with_visual:
        payload["outputs_available"].append("visual_evidence")
        payload["artifacts"]["visual_evidence"] = {
            "filename": "visual_evidence.json",
            "storage_key": f"orgs/{org.id}/jobs/{job.id}/outputs/visual_evidence.json",
        }
        payload["visual_evidence_package_uri"] = payload["artifacts"]["visual_evidence"]["storage_key"]
    if raw_package:
        payload["visual_evidence_package_object"] = {"internal": "raw package must not be public"}

    db_session.add(
        JobOutput(
            job_id=job.id,
            organisation_id=org.id,
            output_type=JobOutputType.HOSTED_MANIFEST,
            json_payload=payload,
            storage_key=f"orgs/{org.id}/jobs/{job.id}/outputs/hosted_manifest.json",
        )
    )
    db_session.commit()
    return org, job


def test_customer_output_catalog_shows_visual_evidence_readiness_from_manifest_without_enum_row(api_client, db_session):
    org, job = _job_with_manifest(db_session, with_visual=True)

    r = api_client.get(
        f"/v1/jobs/{job.id}/outputs/catalog",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org.id},
    )

    assert r.status_code == 200
    outputs = {entry["output_type"]: entry for entry in r.json()["outputs"]}
    visual = outputs["visual_evidence"]
    assert visual["ready"] is True
    assert visual["artifact_available"] is True
    assert visual["evidence_status"] == "ready"
    assert visual["download_url"].endswith("/visual_evidence.json")


def test_customer_outputs_list_includes_visual_evidence_from_manifest_without_db_enum_row(api_client, db_session):
    org, job = _job_with_manifest(db_session, with_visual=True)

    r = api_client.get(
        f"/v1/jobs/{job.id}/outputs",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org.id},
    )

    assert r.status_code == 200
    outputs = {entry["type"]: entry for entry in r.json()["outputs"]}
    assert "visual_evidence" in outputs
    assert outputs["visual_evidence"]["evidence_status"] == "ready"
    assert outputs["visual_evidence"]["download_url"].endswith("/visual_evidence.json")


def test_catalog_does_not_advertise_missing_visual_artifact(api_client, db_session):
    org, job = _job_with_manifest(db_session, with_visual=False)

    r = api_client.get(
        f"/v1/jobs/{job.id}/outputs/catalog",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org.id},
    )

    assert r.status_code == 200
    visual = {entry["output_type"]: entry for entry in r.json()["outputs"]}["visual_evidence"]
    assert visual["ready"] is False
    assert visual["artifact_available"] is False
    assert visual["download_url"] is None
    assert visual["evidence_status"] == "needs_review"


def test_public_hosted_manifest_exposes_status_but_strips_raw_visual_package(api_client, db_session):
    _org, _job = _job_with_manifest(db_session, with_visual=True, raw_package=True)

    r = api_client.get("/v1/manifests/visual-creator/visual-asset.json")

    assert r.status_code == 200
    data = r.json()
    assert data["evidence_status"] == "ready"
    assert data["visual_evidence_available"] is True
    assert data["visual_evidence_package_uri"].endswith("/visual_evidence.json")
    assert "visual_evidence_package_object" not in data


def test_job_status_exposes_visual_evidence_summary_from_manifest(api_client, db_session):
    org, job = _job_with_manifest(db_session, with_visual=True)

    r = api_client.get(
        f"/v1/jobs/{job.id}",
        headers={"Authorization": "Bearer test-internal-key", "X-Org-Id": org.id},
    )

    assert r.status_code == 200
    evidence = r.json()["visual_evidence"]
    assert evidence["artifact_available"] is True
    assert evidence["evidence_status"] == "ready"
    assert evidence["visual_evidence_package_uri"].endswith("/visual_evidence.json")


def test_admin_evidence_view_reads_manifest_artifact_without_visual_enum_row(api_client, db_session):
    org, job = _job_with_manifest(db_session, with_visual=True)

    r = api_client.get(
        f"/v1/admin/jobs/{job.id}/evidence",
        headers={"Authorization": "Bearer test-internal-key"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["evidence_status"] == "ready"
    assert data["artifact_available"] is True
    assert data["visual_evidence_package_uri"].endswith("/visual_evidence.json")


def test_visual_evidence_visibility_does_not_require_db_enum_migration() -> None:
    assert "visual_evidence" not in {item.value for item in JobOutputType}
