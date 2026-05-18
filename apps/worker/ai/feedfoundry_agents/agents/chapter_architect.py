from __future__ import annotations

from ai.feedfoundry_agents.schemas import ChapterArchitectOutput, ChapterOut, FeedFoundryJobInput


def run_chapter_architect(job: FeedFoundryJobInput) -> ChapterArchitectOutput:
    chapters: list[ChapterOut] = []
    for i, seg in enumerate(job.transcript.segments[:12]):
        title = (seg.text or "").strip()[:80] or f"Segment {i + 1}"
        chapters.append(ChapterOut(title=title, start_seconds=float(seg.start), summary=""))
    if not chapters:
        dur = job.media_meta.duration_seconds or 0.0
        chapters = [ChapterOut(title="Full episode", start_seconds=0.0, summary=f"duration_hint={dur}")]
    return ChapterArchitectOutput(chapters=chapters)
