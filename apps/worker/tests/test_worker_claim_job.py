"""Worker job claim advances QUEUED → PROBING (state transition contract)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.models import Job, JobStatus, MediaAsset, MediaAssetStatus, MediaType, Organisation, User

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def sqlite_engine():
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["FF_INTERNAL_API_KEY"] = "test-claim-key"
    os.environ["AI_ROUTING_CONFIG_PATH"] = str(REPO_ROOT / "ai-routing.yaml")
    from app.settings import get_settings

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    get_settings.cache_clear()


def test_claim_next_job_moves_queued_to_probing(sqlite_engine):
    import worker as worker_mod

    org_id = "org_claim"
    ma_id = "ma_claim"
    with Session(sqlite_engine) as session:
        session.add(Organisation(id=org_id, name="C", slug="claim-slug"))
        session.add(User(id="user_claim", organisation_id=org_id, email="c@example.com"))
        session.add(
            MediaAsset(
                id=ma_id,
                organisation_id=org_id,
                original_filename="x.mp4",
                media_type=MediaType.VIDEO,
                storage_source_key="k",
                status=MediaAssetStatus.UPLOADED,
            )
        )
        session.add(
            Job(
                organisation_id=org_id,
                media_asset_id=ma_id,
                status=JobStatus.QUEUED,
                reserved_processing_minutes=10,
                estimated_processing_minutes=10,
                requested_outputs_json=["transcript"],
            )
        )
        session.commit()

    with Session(sqlite_engine) as session:
        job = worker_mod.claim_next_job(session)
        assert job is not None
        assert job.status == JobStatus.PROBING
        assert job.progress_percent == 5
        assert job.current_stage == "Claimed job"
