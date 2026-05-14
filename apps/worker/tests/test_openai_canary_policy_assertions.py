"""Policy assertions for OpenAI canary (split from implementation commit for sprint bookkeeping)."""

from __future__ import annotations

from pathlib import Path

WORKER_AI = Path(__file__).resolve().parents[1] / "ai"


def test_canary_runner_has_no_credit_ledger_import():
    text = (WORKER_AI / "canary_runner.py").read_text(encoding="utf-8")
    assert "credit_ledger" not in text


def test_openai_canary_gates_has_no_credit_ledger_import():
    text = (WORKER_AI / "openai_canary_gates.py").read_text(encoding="utf-8")
    assert "credit_ledger" not in text


def test_registry_has_no_credit_ledger_import():
    text = (WORKER_AI / "registry.py").read_text(encoding="utf-8")
    assert "credit_ledger" not in text
