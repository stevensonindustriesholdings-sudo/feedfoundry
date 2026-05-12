from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.settings import get_settings, r2_s3_endpoint_url


@dataclass
class PresignedUpload:
    upload_url: str
    storage_key: str
    expires_in_seconds: int


def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename) or "source.bin"
    return urllib.parse.unquote(base)


def source_object_key(*, org_id: str, asset_id: str, filename: str) -> str:
    safe = _safe_filename(filename)
    return f"orgs/{org_id}/assets/{asset_id}/source/{safe}"


def job_output_object_key(*, org_id: str, job_id: str, filename: str) -> str:
    """filename e.g. transcript.json, chapters.json"""
    safe = _safe_filename(filename)
    return f"orgs/{org_id}/jobs/{job_id}/outputs/{safe}"


def job_manifest_object_key(*, org_id: str, job_id: str) -> str:
    return f"orgs/{org_id}/jobs/{job_id}/manifest.json"


def _s3_client(settings=None) -> Optional[BaseClient]:
    s = settings or get_settings()
    endpoint = r2_s3_endpoint_url(s)
    key_id = (s.r2_access_key_id or "").strip()
    secret = (s.r2_secret_access_key or "").strip()
    if not endpoint or not key_id or not secret:
        return None
    region = (s.r2_region or "auto").strip() or "auto"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
    )


def bucket_for_source(settings=None) -> str:
    return (settings or get_settings()).r2_bucket_source


def bucket_for_outputs(settings=None) -> str:
    return (settings or get_settings()).r2_bucket_outputs


def presign_put_object(
    *,
    organisation_id: str,
    media_asset_id: str,
    filename: str,
    content_type: Optional[str] = None,
) -> PresignedUpload:
    """Presigned PUT for uploaded source media (R2 source bucket)."""
    settings = get_settings()
    key = source_object_key(org_id=organisation_id, asset_id=media_asset_id, filename=filename)
    expires = settings.storage_presign_put_expires_seconds
    client = _s3_client(settings)
    bucket = bucket_for_source(settings)

    if client is None:
        base = settings.public_api_base_url.rstrip("/")
        url = f"{base}/__dev__/presign-placeholder?bucket={urllib.parse.quote(bucket)}&key={urllib.parse.quote(key)}"
        return PresignedUpload(upload_url=url, storage_key=key, expires_in_seconds=expires)

    params = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    url = client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires,
        HttpMethod="PUT",
    )
    return PresignedUpload(upload_url=url, storage_key=key, expires_in_seconds=expires)


def resolve_bucket_for_storage_key(storage_key: str, settings=None) -> str:
    s = settings or get_settings()
    if "/jobs/" in storage_key and "/outputs/" in storage_key:
        return bucket_for_outputs(s)
    return bucket_for_source(s)


def presign_get_object(
    *,
    bucket: str,
    storage_key: str,
    download_filename: Optional[str] = None,
    settings=None,
) -> str:
    settings = settings or get_settings()
    expires = settings.storage_presign_get_expires_seconds
    client = _s3_client(settings)
    if client is None:
        base = settings.public_api_base_url.rstrip("/")
        q = urllib.parse.quote(storage_key, safe="")
        suffix = f"&filename={urllib.parse.quote(download_filename)}" if download_filename else ""
        return f"{base}/__dev__/download-placeholder?bucket={urllib.parse.quote(bucket)}&key={q}{suffix}"

    params: dict = {"Bucket": bucket, "Key": storage_key}
    if download_filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires,
        HttpMethod="GET",
    )


def head_object_exists(*, bucket: str, key: str, settings=None) -> bool:
    client = _s3_client(settings)
    if client is None:
        return False
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def put_json_bytes(
    *,
    bucket: str,
    key: str,
    body: bytes,
    settings=None,
) -> None:
    client = _s3_client(settings)
    if client is None:
        raise RuntimeError("storage_not_configured")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8",
    )


def build_output_download_url(
    *,
    org_id: str,
    job_id: str,
    filename: str,
    settings=None,
) -> str:
    s = settings or get_settings()
    key = job_output_object_key(org_id=org_id, job_id=job_id, filename=filename)
    return presign_get_object(
        bucket=bucket_for_outputs(s),
        storage_key=key,
        download_filename=filename,
        settings=s,
    )


def presign_get_for_key(
    *,
    storage_key: str,
    download_filename: Optional[str] = None,
    settings=None,
) -> str:
    s = settings or get_settings()
    b = resolve_bucket_for_storage_key(storage_key, s)
    return presign_get_object(
        bucket=b,
        storage_key=storage_key,
        download_filename=download_filename,
        settings=s,
    )


# Back-compat alias used by older routes
def build_source_storage_key(*, organisation_id: str, media_asset_id: str, filename: str) -> str:
    return source_object_key(org_id=organisation_id, asset_id=media_asset_id, filename=filename)
