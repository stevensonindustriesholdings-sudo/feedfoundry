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

## Integration gate

The package can be wired into the existing FeedFoundry agent bundle behind an explicit opt-in flag:

```text
FF_WORKER_VISUAL_EVIDENCE_ENABLED
```

Default is off. With the flag off, `run_feedfoundry_agent_bundle(...)` returns the existing v0.1 bundle shape and does not schedule `visual_evidence_squad`.

With the flag on, the orchestrator:

1. Builds a deterministic visual-evidence input from `FeedFoundryJobInput.transcript`, `visual_frames`, and hosted-manifest hints.
2. Runs `run_visual_evidence_squad(...)` locally.
3. Adds a `visual_evidence` status object to the bundle.
4. Adds evidence fields to `hosted_manifest_hints`, `repository_manifest`, and `geo_freshness`.
5. Appends `visual_evidence_squad` to `run.agents_scheduled`.

## Worker artifact persistence

Experiment 5 persists the flag-on visual-evidence package as a worker output artifact.

Output key/path shape:

```text
orgs/{organisation_id}/jobs/{job_id}/outputs/visual_evidence.json
```

Flag-off behavior:

- no `visual_evidence.json` is written
- no `visual_evidence` output entry is added to the job manifest/export bundle
- existing worker output behavior is unchanged

Flag-on behavior:

1. `maybe_write_agent_bundle(...)` runs the deterministic visual-evidence integration gate.
2. The worker writes the raw `visual_evidence_package_object` to `visual_evidence.json`.
3. The worker reruns/rebuilds the deterministic bundle with `visual_evidence_package_uri` set to the actual persisted storage key.
4. `agent_bundle.json` is then written with matching URI fields on the top-level `visual_evidence`, `hosted_manifest_hints`, `repository_manifest`, and `geo_freshness` objects.
5. The hosted manifest refresh only adds the `visual_evidence` output/artifact reference when the `visual_evidence.json` write succeeded.

Artifact write failure behavior:

- no fake `visual_evidence_package_uri` is emitted
- no `visual_evidence.json` output entry is added to the manifest
- bundle evidence status becomes `artifact_write_failed` and human review remains required
- processing-minute debit/settlement ordering is unchanged; successful-job debit still happens only after output writing returns

The hosted manifest / repository / GEO surfaces must never reference `visual_evidence_package_uri` until the artifact exists.

The exposed evidence fields are:

- `evidence_status`
- `visual_evidence_available`
- `transcript_evidence_available`
- `unsupported_claim_count`
- `human_review_required`
- `final_evidence_confidence`
- `visual_evidence_package_uri`
- `visual_evidence_package_object` on the top-level bundle status only
- `evidence_gate_reason`

Evidence status behavior:

- `ready`: visual evidence exists, transcript evidence exists, unsupported claim count is zero, human review is false, and final evidence confidence is at least `0.75`.
- `needs_review`: weak/missing evidence, unsupported claims, human review required, or confidence below threshold.
- `artifact_write_failed`: visual evidence package generation succeeded but the worker could not persist `visual_evidence.json`; no URI is emitted and hosted manifest/GEO/repository references stay gated.
- `unavailable`: reserved schema value for future explicit media types where visual evidence is intentionally unavailable; current integration gates missing/weak evidence to `needs_review`.

Hosted manifest / GEO / repository surfaces must not imply publishability when `evidence_status != "ready"`. They expose the evidence status and gate reason so later manifest/GEO publication layers can hold or escalate.

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
uv run python -m pytest tests/test_feedfoundry_visual_evidence_integration_gate.py tests/test_feedfoundry_agents_worker_integration.py tests/test_worker_hosted_manifest_agent_bundle.py -q
uv run python scripts/run_feedfoundry_visual_evidence_squad.py
```
