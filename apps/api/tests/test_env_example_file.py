"""Guardrails: example env must stay placeholder-only (no shipped live secrets)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_env_example_avoids_live_secret_patterns():
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "sk_live_" not in lowered
    assert "pk_live_" not in lowered
    assert "rk_live_" not in lowered
    assert "sk_test_replace_me" in lowered
    assert "whsec_replace_me" in lowered


def test_env_example_internal_keys_are_placeholders():
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "FF_INTERNAL_API_KEY=replace_me" in text
    assert "BASE44_WEBHOOK_SECRET=replace_me" in text
