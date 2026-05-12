#!/usr/bin/env python3
"""
Staging / post-deploy smoke checks (non-destructive).

Environment:
  SMOKE_BASE_URL or BASE_URL — API origin, e.g. https://feedfoundry-api-staging.up.railway.app
  SMOKE_INTERNAL_KEY — if set, runs authenticated checks (FF internal key value)
  SMOKE_ORG_ID — organisation header (default: org_dev_demo when using seed data)
  SMOKE_MEDIA_ASSET_ID — optional; with SMOKE_INTERNAL_KEY, POST /v1/jobs then GET job status

Exit code 0 on success, non-zero on failure.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple


def _post_json(
    base: str,
    path: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: float = 30.0,
) -> Tuple[int, bytes]:
    url = _url(base, path)
    data = json.dumps(payload).encode("utf-8")
    h = {
        "User-Agent": "feedfoundry-smoke/1.0",
        "Content-Type": "application/json",
        **headers,
    }
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except OSError as e:
        return -1, repr(e).encode("utf-8")


def _url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def _get(
    base: str,
    path: str,
    *,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> Tuple[int, bytes]:
    url = _url(base, path)
    h = {"User-Agent": "feedfoundry-smoke/1.0"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except OSError as e:
        return -1, repr(e).encode("utf-8")


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"PASS: {msg}")


def main() -> int:
    base = os.environ.get("SMOKE_BASE_URL") or os.environ.get("BASE_URL", "").strip()
    if not base:
        _fail("Set SMOKE_BASE_URL or BASE_URL to the API origin.")
        return 2

    key = os.environ.get("SMOKE_INTERNAL_KEY", "").strip()
    org = os.environ.get("SMOKE_ORG_ID", "org_dev_demo").strip()

    failed = False

    code, body = _get(base, "/health")
    if code == -1:
        _fail(f"/health network error: {body.decode('utf-8', errors='replace')}")
        failed = True
    elif code != 200:
        _fail(f"/health expected 200, got {code}")
        failed = True
    else:
        try:
            data = json.loads(body.decode("utf-8"))
            if data.get("status") != "ok":
                _fail(f"/health unexpected body: {data}")
                failed = True
            else:
                _ok("/health liveness")
        except json.JSONDecodeError:
            _fail("/health not JSON")
            failed = True

    code, body = _get(base, "/ready")
    if code == -1:
        _fail(f"/ready network error: {body.decode('utf-8', errors='replace')}")
        failed = True
    elif code not in (200, 503):
        _fail(f"/ready unexpected status {code}")
        failed = True
    else:
        try:
            data = json.loads(body.decode("utf-8"))
            if "checks" not in data or "ready" not in data:
                _fail(f"/ready missing keys: {data.keys()}")
                failed = True
            else:
                _ok(f"/ready structure (http {code}, overall_ready={data.get('ready')})")
        except json.JSONDecodeError:
            _fail("/ready not JSON")
            failed = True

    code, _body = _get(base, "/openapi.json")
    if code == -1:
        _fail("/openapi.json network error")
        failed = True
    elif code != 200:
        _fail(f"/openapi.json expected 200, got {code}")
        failed = True
    else:
        _ok("/openapi.json")

    code, body = _get(base, "/docs")
    if code == -1:
        _fail("/docs network error")
        failed = True
    elif code != 200:
        _fail(f"/docs expected 200, got {code}")
        failed = True
    else:
        if b"swagger" not in body.lower() and b"openapi" not in body.lower():
            _fail("/docs body does not look like API docs")
            failed = True
        else:
            _ok("/docs reachable")

    if key:
        h = {
            "Authorization": f"Bearer {key}",
            "X-Org-Id": org,
        }
        code, body = _get(base, "/v1/account/credits", headers=h)
        if code == -1:
            _fail("/v1/account/credits network error")
            failed = True
        elif code == 404:
            _ok("/v1/account/credits returns 404 (no annual_access row — expected if not seeded)")
        elif code == 200:
            _ok("/v1/account/credits returns 200")
        elif code == 401:
            _fail("/v1/account/credits 401 — check SMOKE_INTERNAL_KEY matches FF_INTERNAL_API_KEY")
            failed = True
        else:
            _fail(f"/v1/account/credits unexpected {code}: {body[:200]!r}")
            failed = True

        pcode, pbody = _post_json(
            base,
            "/v1/uploads/presign",
            {
                "filename": "smoke.mp4",
                "content_type": "video/mp4",
                "file_size_bytes": 1024,
                "media_type": "video",
            },
            headers=h,
        )
        if pcode == -1:
            _fail(f"/v1/uploads/presign network error: {pbody.decode('utf-8', errors='replace')}")
            failed = True
        elif pcode in (200, 400, 403):
            _ok(f"/v1/uploads/presign responded {pcode} (400/403 acceptable if entitlement/R2 missing)")
        else:
            _fail(f"/v1/uploads/presign unexpected {pcode}: {pbody[:200]!r}")
            failed = True
    else:
        print("SKIP: authenticated checks (set SMOKE_INTERNAL_KEY + SMOKE_ORG_ID)")

    media_id = os.environ.get("SMOKE_MEDIA_ASSET_ID", "").strip()
    if key and media_id:
        h = {
            "Authorization": f"Bearer {key}",
            "X-Org-Id": org,
        }
        jcode, jbody = _post_json(
            base,
            "/v1/jobs",
            {"media_asset_id": media_id, "requested_outputs": ["transcript"]},
            headers=h,
        )
        if jcode == -1:
            _fail(f"/v1/jobs POST network error: {jbody.decode('utf-8', errors='replace')}")
            failed = True
        elif jcode not in (200, 400, 403, 404):
            _fail(f"/v1/jobs POST unexpected {jcode}: {jbody[:200]!r}")
            failed = True
        elif jcode == 200:
            try:
                job_id = json.loads(jbody.decode("utf-8"))["job_id"]
            except (json.JSONDecodeError, KeyError) as e:
                _fail(f"/v1/jobs response parse error: {e}")
                failed = True
                job_id = ""
            if job_id:
                scode, _ = _get(base, f"/v1/jobs/{job_id}", headers=h)
                if scode == -1:
                    _fail(f"/v1/jobs/{job_id} network error")
                    failed = True
                elif scode != 200:
                    _fail(f"/v1/jobs/{job_id} expected 200, got {scode}")
                    failed = True
                else:
                    _ok("/v1/jobs create + status")
        else:
            _ok(
                f"/v1/jobs POST {jcode} (acceptable if no entitlement, unknown asset, or insufficient credits)"
            )
    elif key:
        print("SKIP: job create/status (set SMOKE_MEDIA_ASSET_ID to a seeded asset id, e.g. ma_dev_demo)")

    code, body = _get(base, "/v1/manifests/demo-creator/episode-001.json")
    if code == -1:
        _fail("/v1/manifests network error")
        failed = True
    elif code == 200:
        _ok("/v1/manifests/.../episode-001.json returns 200")
    elif code == 404:
        _ok("/v1/manifests returns 404 (no manifest yet — acceptable)")
    else:
        _fail(f"/v1/manifests unexpected {code}")
        failed = True

    if failed:
        print("Smoke test finished with failures.", file=sys.stderr)
        return 1
    print("Smoke test finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
