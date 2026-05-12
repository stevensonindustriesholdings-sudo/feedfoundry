"""Sanity: staging smoke script is importable (stdlib only at import time)."""


def test_smoke_staging_module_loads():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "smoke_staging.py"
    spec = importlib.util.spec_from_file_location("smoke_staging_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
