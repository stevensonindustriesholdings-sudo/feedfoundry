from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def sqlite_engine():
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("FF_INTERNAL_API_KEY", "test-internal-key")
    os.environ["DATABASE_URL"] = "sqlite://"
    # Resolve ai-routing.yaml from repo root for estimator tests
    os.environ.setdefault(
        "AI_ROUTING_CONFIG_PATH",
        str(REPO_ROOT / "ai-routing.yaml"),
    )
    from app.settings import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    get_settings.cache_clear()


@pytest.fixture
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    with Session(sqlite_engine) as session:
        yield session


@pytest.fixture
def api_client(sqlite_engine):
    from app.settings import get_settings

    get_settings.cache_clear()

    from app.db import get_session
    from app.main import app

    def override_session() -> Generator[Session, None, None]:
        with Session(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
