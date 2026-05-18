from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "013_joboutputtype_agent_bundle.py"


def test_agent_bundle_enum_migration_adds_uppercase_label() -> None:
    body = MIGRATION.read_text()
    assert "Revision ID: 013_agent_bundle_enum" in body
    assert "down_revision: Union[str, None] = \"012_seed_smoke_org\"" in body
    assert "ALTER TYPE %I ADD VALUE %L" in body
    assert "AGENT_BUNDLE" in body
    assert "agent_bundle'" not in body
