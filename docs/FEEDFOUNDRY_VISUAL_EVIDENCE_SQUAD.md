# FeedFoundry visual/evidence squad

Status: deterministic local placeholder, v0.1.

This squad creates the first visual/evidence package for FeedFoundry without calling providers, touching secrets, touching databases, or changing processing-minute debit behavior.

## Paths

- Module: `apps/worker/ai/feedfoundry_agents/visual_evidence/`
- Fixture: `apps/worker/tests/fixtures/feedfoundry_visual_evidence/tiny_visual_evidence_input.json`
- Tests: `apps/worker/tests/test_feedfoundry_visual_evidence_squad.py`
- CLI smoke: `apps/worker/scripts/run_feedfoundry_visual_evidence_squad.py`
- Smoke output: `apps/worker/artifacts/feedfoundry-visual-evidence/visual_evidence.json`

## Output shape

`run_visual_evidence_squad(raw_input)` returns JSON-ready data with:

- `visual_intelligence`
  - `media_id`
  - `keyframe_id`
  - `timestamp_seconds`
  - `frame_uri`
  - `visual_summary`
  - `confidence_score`

- `ocr_text`
  - detected text
  - bounding region placeholder
  - confidence score
  - keyframe/timestamp evidence pointer

- `entities`
  - entity type: `product`, `object`, `logo`, `person`
  - label
  - confidence
  - evidence pointer
  - risk notes

- `visual_evidence`
  - keyframe reference
  - timestamp
  - artifact URI
  - observation
  - confidence

- `transcript_evidence`
  - transcript chunk id
  - timestamp range
  - quote/text excerpt
  - supported claim flag
  - confidence

- `unsupported_claim_report`
  - claim text
  - source: `transcript`, `visual`, or `generated`
  - support status: `supported`, `unsupported`, or `needs_review`
  - missing evidence reason
  - escalation flag

- `confidence_scores`
  - media confidence
  - OCR confidence
  - visual confidence
  - transcript confidence
  - final evidence confidence

- `escalation_flags`
  - missing transcript evidence
  - missing visual evidence
  - low OCR confidence
  - possible hallucination
  - human review required

- `evidence_gate`
  - input hosted-manifest gate
  - final hosted-manifest publishability gate
  - approval-without-evidence block flag
  - reasons

## Hard rules

- Offline/local-first only.
- No OpenAI/OpenRouter/provider calls.
- No processing-minute debit changes.
- No hosted manifest/GEO publishability approval when required evidence is missing or weak.
- Real OCR/keyframe/object detection can replace the placeholders later behind explicit provider/env gates.
- Weak evidence gates to `hold` or `review`, not `approve`.

## Smoke

From `apps/worker`:

```bash
uv run python -m pytest tests/test_feedfoundry_visual_evidence_squad.py -q
uv run python scripts/run_feedfoundry_visual_evidence_squad.py
```
