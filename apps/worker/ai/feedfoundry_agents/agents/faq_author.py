from __future__ import annotations

from ai.feedfoundry_agents.schemas import FaqAuthorOutput, FaqOut, FeedFoundryJobInput


def run_faq_author(job: FeedFoundryJobInput) -> FaqAuthorOutput:
    blob = " ".join((s.text or "").strip() for s in job.transcript.segments[:3]).strip()
    faqs = [
        FaqOut(question="What is this episode about?", answer=blob[:400] or "Content not available in stub."),
        FaqOut(
            question="Where do chapters come from?",
            answer="Chapters are derived from transcript timing in deterministic v0.1.",
        ),
    ]
    return FaqAuthorOutput(faqs=faqs)
