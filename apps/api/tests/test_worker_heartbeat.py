from sqlmodel import Session, select

from app.models import WorkerHeartbeat, utcnow


def test_worker_heartbeat_upsert(db_session: Session):
    wid = "test_worker_1"
    db_session.add(
        WorkerHeartbeat(
            worker_id=wid,
            last_seen_at=utcnow(),
            hostname="h1",
            app_env="test",
            git_commit="abc",
            build_timestamp="t1",
            api_version="0.1.0",
        )
    )
    db_session.commit()

    row = db_session.get(WorkerHeartbeat, wid)
    assert row is not None
    row.hostname = "h2"
    db_session.add(row)
    db_session.commit()

    rows = db_session.exec(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == wid)).all()
    assert len(rows) == 1
    assert rows[0].hostname == "h2"
