"""Predictable auth / header errors for internal org routes."""


def test_jobs_missing_bearer_returns_401(api_client):
    r = api_client.post(
        "/v1/jobs",
        headers={"X-Org-Id": "org_x"},
        json={"media_asset_id": "ma_x", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or missing credentials"


def test_jobs_wrong_bearer_returns_401(api_client):
    r = api_client.post(
        "/v1/jobs",
        headers={
            "Authorization": "Bearer not-the-test-key",
            "X-Org-Id": "org_x",
        },
        json={"media_asset_id": "ma_x", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or missing credentials"


def test_jobs_missing_org_header_returns_400(api_client):
    r = api_client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer test-internal-key"},
        json={"media_asset_id": "ma_x", "requested_outputs": ["transcript"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "X-Org-Id or X-FF-Organisation-Id required"


def test_presign_accepts_legacy_internal_header(api_client, db_session):
    from datetime import timedelta

    from app.models import AnnualAccess, CreditWallet, Organisation, User, utcnow

    org_id = "org_legacy_hdr"
    db_session.add(Organisation(id=org_id, name="L", slug="leg-hdr"))
    db_session.add(User(id="user_lh", organisation_id=org_id, email="lh@example.com"))
    now = utcnow()
    db_session.add(
        AnnualAccess(
            organisation_id=org_id,
            plan_code="creator_core",
            period_start=now,
            period_end=now + timedelta(days=365),
            hosting_until=now + timedelta(days=365),
            included_credits=100,
        )
    )
    db_session.add(CreditWallet(organisation_id=org_id, balance_available=200))
    db_session.commit()

    r = api_client.post(
        "/v1/uploads/presign",
        headers={
            "X-FF-Internal-Key": "test-internal-key",
            "X-Org-Id": org_id,
        },
        json={
            "filename": "x.m4a",
            "content_type": "audio/mp4",
            "file_size_bytes": 5000,
            "media_type": "audio",
        },
    )
    assert r.status_code == 200
    assert r.json()["media_asset_id"]
