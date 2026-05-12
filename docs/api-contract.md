# API contract (V1)

Base path: `/v1`. Authenticated requests use `X-FF-Internal-Key` (server-side only; Base44 backend function or trusted proxy).

## Health

`GET /v1/health`

Response:

```json
{
  "status": "ok",
  "service": "feedfoundry-api",
  "version": "0.1.0"
}
```

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
  "storage_key": "org_123/uploads/ma_123/source.mp4",
  "expires_in_seconds": 900
}
```

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

Response:

```json
{
  "job_id": "job_123",
  "status": "queued",
  "estimated_credits": 18,
  "reserved_credits": 18
}
```

## Job status

`GET /v1/jobs/{job_id}`

Response:

```json
{
  "job_id": "job_123",
  "status": "generating_outputs",
  "progress_percent": 72,
  "current_stage": "Creating Fact Sheet and FAQs",
  "estimated_credits": 18,
  "reserved_credits": 18,
  "actual_credits_so_far": 12
}
```

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

## Credits

`GET /v1/account/credits`

Response:

```json
{
  "annual_access_status": "active",
  "hosting_until": "2027-05-12",
  "credits_available": 214,
  "credits_reserved": 18,
  "credits_spent_lifetime": 86,
  "next_credit_expiry": "2027-05-12"
}
```

## Hosted manifest

`GET /v1/manifests/{creator_slug}/{asset_slug}.json`

Returns Hosted Manifest JSON (public or semi-public).
