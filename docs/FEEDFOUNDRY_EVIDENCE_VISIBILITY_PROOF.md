# FeedFoundry evidence visibility proof

Status: Experiment 7 closeout proof for customer/admin visual evidence visibility.

This proof does not call live providers, does not touch secrets, does not mutate production databases, and does not change processing-minute debit behavior.

## What is proved

- A job can expose `visual_evidence.evidence_status` through `GET /v1/jobs/{job_id}` when the persisted hosted manifest row has evidence fields.
- Customer output catalog can show visual evidence readiness from `hosted_manifest.json` without requiring a `visual_evidence` DB enum row.
- Admin can read the evidence summary through `GET /v1/admin/jobs/{job_id}/evidence`.
- Public hosted manifest responses expose safe status fields.
- `visual_evidence_package_object` is stripped from the public hosted manifest response.
- Download URL is emitted only when `artifacts.visual_evidence.storage_key` exists.
- Missing artifact storage key does not create a fake URI.

## Local proof commands

From `apps/api`:

```bash
uv run pytest tests/test_visual_evidence_visibility.py -q
uv run pytest tests/test_visual_evidence_visibility.py tests/test_admin_agent_bundle.py tests/test_vertical_slice.py tests/test_upload_job_workflow.py tests/test_job_states.py tests/test_job_cancellation.py -q
```

From `apps/worker`:

```bash
PYTHONPATH=.:../api uv run python -m pytest tests/test_feedfoundry_visual_evidence_integration_gate.py tests/test_feedfoundry_agents_worker_integration.py tests/test_worker_hosted_manifest_agent_bundle.py tests/test_feedfoundry_visual_evidence_squad.py -q
uv run python scripts/run_feedfoundry_visual_evidence_squad.py
```

## Provider/network/secrets audit

The visual evidence visibility path is API-only manifest reading. It does not introduce provider calls. A broad grep will still find existing provider-gated code elsewhere in FeedFoundry, so verify the visibility implementation directly:

```bash
rg "httpx|requests|OPENAI|OPENROUTER|HYPERFRAMES_API_KEY|FEEDFOUNDRY_INTERNAL_API_TOKEN" apps/api/app/services/evidence_visibility.py apps/api/app/routes/{jobs,outputs,manifests,admin}.py apps/api/tests/test_visual_evidence_visibility.py
```

Expected result: no matches in the visibility implementation/test files.

## Surfaces

- Customer job status: `GET /v1/jobs/{job_id}`
- Customer output list: `GET /v1/jobs/{job_id}/outputs`
- Customer output catalog: `GET /v1/jobs/{job_id}/outputs/catalog`
- Admin evidence summary: `GET /v1/admin/jobs/{job_id}/evidence`
- Public hosted manifest: `GET /v1/manifests/{creator_slug}/{asset_slug}.json`

## Safety rules retained

- `FF_WORKER_VISUAL_EVIDENCE_ENABLED` remains default off.
- No visual evidence artifact is invented when the flag is off.
- No fake evidence URI is emitted when artifact storage key is missing.
- Public hosted manifest does not expose raw `visual_evidence_package_object`.
- Processing-minute debit behavior remains governed by the existing worker completion path.
