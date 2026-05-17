"""Guards for Postgres ``jobstatus`` migration behaviour (006 text cast + 009 optional label)."""

from pathlib import Path


def _read_migration(name_fragment: str) -> str:
    root = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    matches = sorted(root.glob(f"*{name_fragment}*.py"))
    assert len(matches) == 1, f"expected one migration matching {name_fragment}, got {matches}"
    return matches[0].read_text()


def test_006_job_status_update_compares_text_not_enum_literals():
    """Enum columns reject string literals that are not enum labels; compare via ::text."""
    sql = _read_migration("006_processing_minutes")
    assert "status::text" in sql
    assert "WHERE status::text IN" in sql
    assert ")::jobstatus" in sql


def test_009_adds_created_label_idempotently():
    body = _read_migration("009_jobstatus_created")
    assert "pg_catalog.pg_enum" in body
    assert "enumlabel = 'created'" in body
    assert "ALTER TYPE jobstatus ADD VALUE 'created'" in body
