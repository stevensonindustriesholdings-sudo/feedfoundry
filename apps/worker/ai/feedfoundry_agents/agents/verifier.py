from __future__ import annotations

from ai.feedfoundry_agents.schemas import (
    FeedFoundryAgentBundleOutput,
    FeedFoundryJobInput,
    VerifierIssue,
    VerifierOutput,
)


def run_verifier(job: FeedFoundryJobInput, draft: FeedFoundryAgentBundleOutput) -> VerifierOutput:
    issues: list[VerifierIssue] = []
    for c in draft.ctas.ctas:
        if c.url and c.url.startswith("http"):
            issues.append(
                VerifierIssue(
                    code="BLOCK_external_cta_url",
                    message="CTA URLs must not be invented http(s) links in v0.1 bundle.",
                    agent_id="cta_designer",
                )
            )
    if not draft.chapters.chapters:
        issues.append(VerifierIssue(code="WARN_no_chapters", message="Chapter list empty.", agent_id="chapter_architect"))
    passed = not any(i.code.startswith("BLOCK_") for i in issues)
    return VerifierOutput(passed=passed, issues=issues)
