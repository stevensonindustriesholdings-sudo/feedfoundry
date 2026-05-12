import importlib.util
from pathlib import Path

import pytest


def test_seed_refused_in_production_without_flag(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "seed_dev.py"
    spec = importlib.util.spec_from_file_location("seed_dev_guarded", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOW_DEV_SEED", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    with pytest.raises(SystemExit):
        mod.seed()
