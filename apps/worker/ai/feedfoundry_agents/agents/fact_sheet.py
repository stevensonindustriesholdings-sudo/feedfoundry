from __future__ import annotations

from ai.feedfoundry_agents.schemas import FactLineOut, FactSheetOutput, FeedFoundryJobInput


def run_fact_sheet(job: FeedFoundryJobInput) -> FactSheetOutput:
    facts: list[FactLineOut] = []
    for i, seg in enumerate(job.transcript.segments[:8]):
        t = (seg.text or "").strip()
        if not t:
            continue
        facts.append(FactLineOut(statement=t[:240], source_span=f"seg:{i}"))
    if not facts:
        facts = [FactLineOut(statement="No extractive facts — empty transcript input.", source_span=None)]
    return FactSheetOutput(facts=facts)
