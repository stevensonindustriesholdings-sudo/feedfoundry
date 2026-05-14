# API contract (V1)

Base path: `/v1`. Authenticated requests use **`Authorization: Bearer`** with the same value as server **`FF_INTERNAL_API_KEY`**, plus **`X-Org-Id: {organisation_id}`** (or your deployment’s org header convention).

**Errors (4xx/5xx):** flat JSON body:

```json
{"code": "machine_readable_code", "message": "Human-readable message.", "fields": []}
```

## Health

`GET /v1/health` (legacy) — same shape as root health where exposed.

## Presign upload

`POST /v1/uploads/presign`

Request:

```json
{
  "filename": "episode-014.mp4",
  "content_type": "video/mp4",
  "file_size_bytes": 1840000000,
  "media_type": "video"
}
```

Response:

```json
{
  "media_asset_id": "ma_123",
  "upload_url": "signed-upload-url",
  "storage_key": "orgs/org_123/assets/ma_123/source/episode-014.mp4",
  "expires_in_seconds": 900
}
```

## Upload complete

`POST /v1/uploads/complete`

After the client `PUT`s bytes to `upload_url`, call complete so the asset is ready for job creation.

```json
{ "media_asset_id": "ma_123" }
```

## Output kinds catalog

`GET /v1/catalog/outputs` — doctrine output slugs/titles for job requests.

## Create job

`POST /v1/jobs`

Request:

```json
{
  "media_asset_id": "ma_123",
  "requested_outputs": [
    "transcript",
    "chapters",
    "show_notes",
    "metadata",
    "ctas",
    "fact_sheet",
    "faqs",
    "hosted_manifest",
    "export_bundle"
  ],
  "distribution_targets": ["youtube", "podcast", "patreon", "website"]
}
```

Response (canonical fields; optional **`*_credits`** keys may appear as **deprecated compatibility aliases** mirroring the minute fields):

```json
{
  "job_id": "job_123",
  "status": "queued",
  "estimated_processing_minutes": 18,
  "reserved_processing_minutes": 18,
  "estimated_processing_hours": 0.3
}
```

## List jobs

`GET /v1/jobs?status=&limit=&offset=` — filter optional; paging via `limit` / `offset`.

## Job status

`GET /v1/jobs/{job_id}`

Customer-visible **`status`** values include: `uploaded`, `queued`, `processing`, `completed`, `failed`, `cancelled`.

Response (excerpt):

```json
{
  "job_id": "job_123",
  "status": "processing",
  "progress_percent": 72,
  "current_stage": "transcribing",
  "estimated_processing_minutes": 18,
  "reserved_processing_minutes": 18,
  "actual_processing_minutes_charged": null,
  "estimated_processing_hours": 0.3
}
```

## Cancel job

`POST /v1/jobs/{job_id}/cancel` — releases reserved processing minutes when the job is in a cancellable state; **cancelled** jobs do not consume completed allowance like **completed** jobs.

## Job outputs

`GET /v1/jobs/{job_id}/outputs`

Response:

```json
{
  "job_id": "job_123",
  "outputs": [
    {
      "type": "fact_sheet",
      "title": "Fact Sheet",
      "format": "markdown",
      "download_url": "signed-download-url"
    }
  ]
}
```

## Job outputs catalog

`GET /v1/jobs/{job_id}/outputs/catalog` — per-job doctrine slots with `ready` flags and optional URLs.

## Account (processing allowance)

Canonical:

- `GET /v1/account`
- `GET /v1/account/usage`

Response (canonical fields; optional **`*_credits`** keys may appear as **deprecated compatibility aliases**):

```json
{
  "annual_archive_access_status": "active",
  "hosting_until": "2027-05-12T00:00:00Z",
  "processing_minutes_available": 214,
  "processing_minutes_reserved": 18,
  "processing_minutes_used_lifetime": 86,
  "processing_hours_available": 3.57,
  "processing_period_ends_on": null
}
```

**Deprecated compatibility alias only:** `GET /v1/account/credits` — same JSON as above; prefer **`/v1/account`** or **`/v1/account/usage`**. Do not describe “credits” as the customer-facing model.

## Hosted manifest

`GET /v1/manifests/{creator_slug}/{asset_slug}.json`

Returns Hosted Manifest JSON (public or semi-public).
