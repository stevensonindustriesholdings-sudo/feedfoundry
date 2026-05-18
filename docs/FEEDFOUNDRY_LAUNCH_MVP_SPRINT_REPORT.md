# FeedFoundry launch MVP sprint report

Running log for **launch MVP intake + portal + worker YouTube stub path** (2026-05-18).

## Hermes / execution lane proof

```json
{
  "hermes_acp_check": "NOT_RUN",
  "hermes_smoke": "NOT_RUN",
  "execution_lane": "cursor_only",
  "direct_openai_or_openrouter_used": false,
  "agent_stack_or_skill_used": false,
  "agent_stack_or_skill_name": "",
  "proof_artifacts": ["docs/FEEDFOUNDRY_LAUNCH_MVP_SPRINT_REPORT.md", "scripts/smoke_launch_mvp.sh"],
  "notes": "Implementation and verification done in Cursor; Hermes ACP not invoked for this slice."
}
```

## Phase 0 — Repo scan (summary)

| Area | Finding |
|------|---------|
| Branch | `feat/feedfoundry-launch-mvp-flow` (continues `feat/feedfoundry-hermes-agent-stack` work including `c30e136`, `58289f0`) |
| Jobs API | `GET/POST /v1/jobs`, `GET /v1/jobs/{id}`, outputs at `GET /v1/jobs/{id}/outputs` |
| YouTube queue | Existing `POST/GET /v1/youtube-source-queue` (enqueue-only); extended rows for intake linkage |
| Credits | Reserve on `POST /v1/jobs`; worker `_settle_processing_allowance` only after `_write_stub_outputs` succeeds |
| Agent bundle | `FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED`; failures → `JobProcessingFailure` → `fail_job` releases reserve (no debit) |
| OpenAI | Worker transcript v0 uses `openai_api_key` when present; no new `FF_WORKER_AI_ENRICHMENT_*` wiring (names surfaced in `/v1/system/worker-hints` for next step) |

## Phase 2 — Intake API (implemented)

| Method | Path | Behaviour |
|--------|------|-------------|
| POST | `/v1/intake/youtube-video` | Requires `FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED`; validates watch URL; creates `youtube_source_queue` + `media_assets` (`intake_kind=youtube_stub`, `storage_source_key=ff-youtube-pending:{queue_id}`) + `POST /v1/jobs` equivalent |
| POST | `/v1/intake/youtube-playlist` | Same gate; validates `youtube.com` URL with `list=`; parent row `status=not_yet_expanded`, **no job** |
| POST | `/v1/intake/upload` | `CreateJobRequest` + optional `duration_seconds` (updates media hint) then same job create as `/v1/jobs` |

## Phase 3 — Source acquisition

- **Upload:** unchanged presign → PUT → optional `/v1/uploads/complete` → `/v1/intake/upload` or `/v1/jobs`.
- **YouTube:** `apps/worker/youtube_acquisition.py` stub documents `FF_YOUTUBE_SOURCE_ACQUISITION_LIVE`. Worker treats `intake_kind=youtube_stub` like “no source file” and runs deterministic stub outputs (no FFmpeg/transcript from media file).
- Queue fields: `acquisition_status`, `acquisition_error`, `source_title`, `source_duration_seconds`, `temp_media_storage_key` (Postgres via Alembic `010_launch_mvp_intake_fields`).

## Phase 4–5 — Worker / OpenAI

- Settlement order unchanged: `_write_stub_outputs` → `_finalize_youtube_stub_queue` → `_settle_processing_allowance` → completed.
- `FF_WORKER_AI_ENRICHMENT_ENABLED` reserved in worker-hints only (no router wiring in this sprint).

## Phase 6 — Portal `/portal`

- Credits (`GET /v1/account/credits`), worker hints, YouTube video + playlist intake, upload→job, org queue table, jobs list, job detail + output downloads + JSON previews (manifest, metadata, CTAs, FAQs, etc.).

## Phase 8 — Tests

- `apps/api/tests/test_intake_launch_mvp.py` — gate off/on, video creates stub media+job, playlist parent only, intake upload.
- Worker: existing agent bundle + manifest tests (`PYTHONPATH=.:../api`).

## Phase 9 — Smoke

- `scripts/smoke_launch_mvp.sh` — API import, web typecheck/build, agent bundle CLI, intake pytest, worker bundle tests.

## Phase 10 — Deployment plan (commands only; no secret values)

From repo root (after push):

```bash
git push -u origin feat/feedfoundry-launch-mvp-flow
```

Railway (service names from `docs/deployment-railway.md`): **`api-v2-IQho`**, **`worker-v2`**. Typical CLI pattern (adjust project link):

```bash
railway service api-v2-IQho -- railway up
railway service worker-v2 -- railway up
```

Web app deploy depends on your hosting (Vercel/Railway static); not prescribed here.

### Env var **names** (values never committed)

| Name | Purpose |
|------|---------|
| `FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED` | Gate `POST /v1/intake/youtube-video` and `/youtube-playlist` |
| `FF_YOUTUBE_SOURCE_ACQUISITION_LIVE` | Future real acquisition path (stub until implemented) |
| `FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED` | Worker writes `agent_bundle.json` |
| `FF_WORKER_AI_ENRICHMENT_ENABLED` | Reserved hint for capped worker-side enrichment |
| `FF_SKIP_SOURCE_VERIFY` | Dev/staging bypass for missing R2 object (existing) |
| `FF_STRICT_SOURCE_VERIFY` | Force strict source HEAD (existing) |
| `FF_SOURCE_HEAD_MAX_WAIT_SECONDS` | R2 read-after-write wait (existing) |
| `DATABASE_URL` | API + worker |
| `FF_INTERNAL_API_KEY` | API |
| `FEEDFOUNDRY_INTERNAL_API_KEY` | Web BFF → API |
| R2 / storage vars | As in `app.settings` |

## Blockers / follow-ups

- **Sign-in:** Still internal-key + org header BFF model (same as `/upload`); no new end-user OAuth in this slice.
- **Playlist expansion:** Not implemented; parent rows only.
- **Real YouTube download:** Behind `FF_YOUTUBE_SOURCE_ACQUISITION_LIVE` + implementation in `youtube_acquisition.py`.
- **Hermes:** Not run for this change set (see proof block).

## First live smoke (after deploy)

1. Set `FF_YOUTUBE_SOURCE_ACQUISITION_ENABLED=1` on API (and matching web proxy if needed).
2. Open `/portal` → confirm credits + hints.
3. Submit a public watch URL → job appears in list → wait for worker → downloads + manifest preview.
4. Toggle `FF_FEEDFOUNDRY_AGENT_BUNDLE_ENABLED` on worker only → rerun job; confirm `agent_bundle` only when file exists.

## Tests run (agent)

- `scripts/smoke_launch_mvp.sh` — PASS
- `npm run typecheck` / `npm run build` in `apps/web` — PASS
