# Real media verification sprint

This note covers **staging** verification with real uploads, **strict source verify** on **worker-v2** only, and the **`media_inspection.json`** output. Railway changes apply only to **`api-v2-IQho`** and **`worker-v2`** — not legacy API/worker services.

## Prerequisites

- Staging API base URL (public Railway host for **api-v2-IQho**).
- `FF_INTERNAL_API_KEY` matching the API service (Bearer token).
- Seeded org with annual access and credits (e.g. `scripts/seed_dev.py` on staging DB → `org_dev_demo`).
- R2 credentials on **both** API and worker; worker image includes **ffmpeg/ffprobe** (`apps/worker/Dockerfile` installs `ffmpeg`, which provides `ffprobe`).
- Run Alembic so Postgres knows the new enum value: `004_joboutputtype_media_inspection` (`media_inspection` on `joboutputtype`).

## 1. Real upload smoke path

1. Obtain a **small real MP4** on your machine, for example:
   - `curl -L -o /tmp/smoke.mp4 'https://filesamples.com/samples/video/mp4/sample_960x540.mp4'` (pick any small file your network allows), or  
   - `docker run --rm -v /tmp:/out jrottenberg/ffmpeg:4.4-alpine -y -f lavfi -i testsrc=duration=1:size=320x240:rate=1 -c:v libx264 -pix_fmt yuv420p /out/smoke.mp4` if you prefer a local generator.
2. Export:
   - `SMOKE_BASE_URL` — `https://<your-staging-api-host>` (same as `BASE_URL` in other scripts).
   - `SMOKE_INTERNAL_KEY` — same value as `FF_INTERNAL_API_KEY` on **api-v2-IQho**.
   - `SMOKE_ORG_ID` — e.g. `org_dev_demo`.
   - `SMOKE_MP4_PATH` — path to the file, e.g. `/tmp/smoke.mp4`.
3. Run:

   ```bash
   python3 tools/smoke_real_media_upload.py
   ```

Flow implemented by the script: **POST** `/v1/uploads/presign` → **PUT** bytes to `upload_url` (expect **2xx**) → **POST** `/v1/jobs` with returned `media_asset_id` → poll **GET** `/v1/jobs/{job_id}` until `complete` → **GET** `/v1/jobs/{job_id}/outputs`.

**Output count:** With R2 + a present source object + successful ffprobe, the worker writes the **six** existing stub JSON files plus **`media_inspection.json`** → **seven** `JobOutput` rows (and seven entries in `manifest.json` under `outputs`). If the worker has **no** S3 client, or staging **continues without a source object** (see below), inspection is skipped → **six** outputs. The script prints output `type` values so you can see whether `media_inspection` is present.

Do **not** commit API keys; use env vars or a local `.env` that stays untracked.

## 2. Strict source verify (`FF_STRICT_SOURCE_VERIFY`)

After the PUT smoke path succeeds against R2:

1. In Railway, open service **`worker-v2`** → **Variables**.
2. Set **`FF_STRICT_SOURCE_VERIFY=1`** (exact name).
3. Redeploy **worker-v2** so the process picks up the variable.

Behaviour (see `apps/worker/worker.py` `process_job`): if the source object is **missing** and `APP_ENV=staging`, the worker **warns and continues** with stubs **only when** strict mode is **off**. With **`FF_STRICT_SOURCE_VERIFY=1`**, a missing object raises **`source_object_missing`** (same as non-staging). With a successful PUT, **HEAD** passes and processing (including ffprobe) proceeds.

Do **not** set `FF_STRICT_SOURCE_VERIFY` on legacy worker services.

## 3. `media_inspection.json`

The worker streams the source object to a temp file via **`download_fileobj`** (`download_object_to_tempfile` in `apps/api/app/services/storage.py`), runs **`ffprobe -v quiet -print_format json -show_format -show_streams`**, then writes **`media_inspection.json`** to the outputs bucket and registers **`JobOutputType.MEDIA_INSPECTION`**. Payload includes `duration_seconds`, `container_format` (`format_name`), `video_codec`, `audio_codec`, `file_size_bytes`, and **`chunk_plan`** from `plan_chunks` in `apps/worker/pipeline/chunk_plan.py`. Existing stub outputs are unchanged.

## 4. Failed job note

Ignore historical failed job **`job_d017dbbe9ed9`** for pass/fail of this sprint.
