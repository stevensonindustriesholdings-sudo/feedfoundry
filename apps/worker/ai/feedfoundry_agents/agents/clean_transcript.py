from __future__ import annotations

import re

from ai.feedfoundry_agents.schemas import CleanTranscriptOutput, FeedFoundryJobInput


def run_clean_transcript(job: FeedFoundryJobInput) -> CleanTranscriptOutput:
    paras: list[str] = []
    buf: list[str] = []
    for seg in job.transcript.segments:
        t = re.sub(r"\s+", " ", (seg.text or "").strip())
        if not t:
            continue
        buf.append(t)
        if len(" ".join(buf)) > 220:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    if not paras:
        paras = ["[no transcript text]"]
    return CleanTranscriptOutput(paragraphs=paras[:24])
