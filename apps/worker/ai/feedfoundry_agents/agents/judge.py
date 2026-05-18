from __future__ import annotations

from ai.feedfoundry_agents.schemas import JudgeOutput, JudgeVerdict, VerifierOutput


def run_judge(verification: VerifierOutput) -> JudgeOutput:
    if verification.passed:
        if verification.issues:
            return JudgeOutput(verdict=JudgeVerdict.PASS_WITH_NOTES, rationale="No blockers; warnings only.")
        return JudgeOutput(verdict=JudgeVerdict.PASS, rationale="Verifier passed with zero issues.")
    return JudgeOutput(verdict=JudgeVerdict.BLOCKED, rationale="Verifier reported blocking issues.")
