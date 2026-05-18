"""Verifier + judge arbitration on blocking issues."""

from __future__ import annotations

from pathlib import Path

from ai.feedfoundry_agents.agents.judge import run_judge
from ai.feedfoundry_agents.agents.verifier import run_verifier
from ai.feedfoundry_agents.orchestrator import run_feedfoundry_agent_bundle
from ai.feedfoundry_agents.schemas import (
    CtaDesignerOutput,
    CtaOut,
    FeedFoundryAgentBundleOutput,
    FeedFoundryJobInput,
    JudgeVerdict,
    VerifierOutput,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "feedfoundry_agents"


def test_feedfoundry_agents_verifier_judge_pass() -> None:
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    bundle = run_feedfoundry_agent_bundle(job)
    assert bundle.verification.passed is True
    assert bundle.judge.verdict == JudgeVerdict.PASS


def test_feedfoundry_agents_verifier_judge_blocks_on_http_cta() -> None:
    job = FeedFoundryJobInput.model_validate_json((FIXTURE_DIR / "tiny_job_input.json").read_text(encoding="utf-8"))
    base = run_feedfoundry_agent_bundle(job)
    bad_ctas = CtaDesignerOutput(
        ctas=[CtaOut(label="Bad", intent="external", url="https://example.com/promo")]
    )
    tampered = FeedFoundryAgentBundleOutput.model_validate({**base.model_dump(), "ctas": bad_ctas.model_dump()})
    v = run_verifier(job, tampered)
    assert v.passed is False
    j = run_judge(v)
    assert j.verdict == JudgeVerdict.BLOCKED
