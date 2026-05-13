#!/usr/bin/env python3
"""
End-to-end smoke: presign → PUT source → create job → poll → list outputs.

Requires a small MP4 on disk (generate with host ffmpeg, or download once with curl).
Does not commit secrets; reads from the environment.

Environment:
  SMOKE_BASE_URL or BASE_URL — staging API origin (e.g. https://…railway.app)
  SMOKE_INTERNAL_KEY — Bearer value (same as FF_INTERNAL_API_KEY on api-v2-IQho)
  SMOKE_ORG_ID — X-Org-Id (e.g. org_dev_demo after seed)
  SMOKE_MP4_PATH — path to a small real .mp4 file to upload

Optional:
  SMOKE_POLL_SECONDS — default 5
  SMOKE_JOB_TIMEOUT_SECONDS — default 600
  SMOKE_REQUIRE_AUDIO=1 — assert media_inspection.audio_codec present, transcript audio_extraction
    shows extracted audio (has_audio / has_audio_stream), metadata fields, and source is
    transcript_stub unless SMOKE_ALLOW_OPENAI_TRANSCRIPT=1 (worker has OpenAI path).

Successful completion expects worker-v2 to finish the job. Output count is **7**
when R2 is configured and media_inspection.json is written (6 transcript-linked artefacts
+ inspection), or **6** when the worker has no S3 client / staging missing-source continuation / etc.
Chapters, fact_sheet, faqs, metadata, and hosted_manifest are **deterministically derived**
from raw_transcript + media_inspection (v0 — no LLM). The script validates ``derived_from``,
``outputs_available`` on hosted_manifest, and that chapter titles reflect transcript text.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Tuple


def _post_json(
    base: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout: float = 120.0,
) -> Tuple[int, bytes]:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8")
    h = {
        "User-Agent": "feedfoundry-smoke-real-media/1.0",
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


def _get_url(url: str, *, timeout: float = 60.0) -> Tuple[int, bytes]:
    h = {"User-Agent": "feedfoundry-smoke-real-media/1.0"}
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except OSError as e:
        return -1, repr(e).encode("utf-8")


def _get(
    base: str,
    path: str,
    headers: dict[str, str],
    *,
    timeout: float = 60.0,
) -> Tuple[int, bytes]:
    url = f"{base.rstrip('/')}{path}"
    h = {"User-Agent": "feedfoundry-smoke-real-media/1.0", **headers}
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except OSError as e:
        return -1, repr(e).encode("utf-8")


def _fetch_output_json(outputs: list[dict[str, Any]], output_type: str) -> tuple[int, dict[str, Any] | None]:
    o = next((x for x in outputs if x.get("type") == output_type), None)
    if not o:
        return 404, None
    url = o.get("download_url") or ""
    if not url:
        return 400, None
    code, body = _get_url(url, timeout=60.0)
    if code != 200:
        return code, None
    return 200, json.loads(body.decode("utf-8"))


def _put_bytes(url: str, body: bytes, content_type: str, *, timeout: float = 300.0) -> Tuple[int, str]:
    h = {
        "User-Agent": "feedfoundry-smoke-real-media/1.0",
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
    }
    req = urllib.request.Request(url, data=body, headers=h, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode() or 200, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except OSError as e:
        return -1, repr(e)


def main() -> int:
    base = (os.environ.get("SMOKE_BASE_URL") or os.environ.get("BASE_URL") or "").strip()
    key = (os.environ.get("SMOKE_INTERNAL_KEY") or "").strip()
    org = (os.environ.get("SMOKE_ORG_ID") or "org_dev_demo").strip()
    mp4_path = (os.environ.get("SMOKE_MP4_PATH") or "").strip()

    if not base or not key or not mp4_path:
        print(
            "Set SMOKE_BASE_URL (or BASE_URL), SMOKE_INTERNAL_KEY, SMOKE_ORG_ID, "
            "and SMOKE_MP4_PATH to a small .mp4 file.",
            file=sys.stderr,
        )
        return 2

    p = Path(mp4_path)
    if not p.is_file():
        print(f"SMOKE_MP4_PATH not a file: {mp4_path}", file=sys.stderr)
        return 2

    body = p.read_bytes()
    filename = p.name
    content_type = "video/mp4"
    poll_s = float(os.environ.get("SMOKE_POLL_SECONDS", "5"))
    timeout_s = float(os.environ.get("SMOKE_JOB_TIMEOUT_SECONDS", "600"))

    auth = {"Authorization": f"Bearer {key}", "X-Org-Id": org}

    code, raw = _post_json(
        base,
        "/v1/uploads/presign",
        {
            "filename": filename,
            "content_type": content_type,
            "file_size_bytes": len(body),
            "media_type": "video",
        },
        auth,
    )
    if code != 200:
        print(f"presign failed http={code} body={raw[:500]!r}", file=sys.stderr)
        return 1
    pres = json.loads(raw.decode("utf-8"))
    media_asset_id = pres["media_asset_id"]
    upload_url = pres["upload_url"]

    put_code, put_err = _put_bytes(upload_url, body, content_type)
    if put_code < 200 or put_code >= 300:
        print(f"PUT upload failed http={put_code} err={put_err}", file=sys.stderr)
        return 1
    print(f"PUT source ok ({put_code}) media_asset_id={media_asset_id}")

    jcode, jraw = _post_json(
        base,
        "/v1/jobs",
        {"media_asset_id": media_asset_id, "requested_outputs": ["transcript"]},
        auth,
    )
    if jcode != 200:
        print(f"POST /v1/jobs failed http={jcode} body={jraw[:500]!r}", file=sys.stderr)
        return 1
    job_id = json.loads(jraw.decode("utf-8"))["job_id"]
    print(f"job created job_id={job_id}")

    deadline = time.monotonic() + timeout_s
    status = ""
    while time.monotonic() < deadline:
        scode, sbody = _get(base, f"/v1/jobs/{job_id}", auth)
        if scode != 200:
            print(f"GET job status http={scode} body={sbody[:300]!r}", file=sys.stderr)
            return 1
        info = json.loads(sbody.decode("utf-8"))
        status = info.get("status", "")
        print(f"  job status={status} progress={info.get('progress_percent')}")
        if status in ("complete", "failed", "cancelled"):
            break
        time.sleep(poll_s)

    if status != "complete":
        print(f"job did not complete (last status={status})", file=sys.stderr)
        return 1

    ocode, obody = _get(base, f"/v1/jobs/{job_id}/outputs", auth)
    if ocode != 200:
        print(f"GET outputs http={ocode} body={obody[:300]!r}", file=sys.stderr)
        return 1
    outs = json.loads(obody.decode("utf-8")).get("outputs", [])
    types = [o.get("type") for o in outs]
    print(f"outputs count={len(types)} types={types}")
    if len(types) != 7:
        print(f"FAIL: expected 7 outputs, got {len(types)}", file=sys.stderr)
        return 1
    if "media_inspection" not in types:
        print(
            "FAIL: media_inspection missing (need R2 + visible source + worker ffprobe).",
            file=sys.stderr,
        )
        return 1
    print("PASS: media_inspection output present.")
    insp = next(o for o in outs if o.get("type") == "media_inspection")
    url = insp.get("download_url") or ""
    if not url:
        print("FAIL: media_inspection has no download_url", file=sys.stderr)
        return 1
    icode, ibody = _get_url(url, timeout=60.0)
    if icode != 200:
        print(f"FAIL: fetch inspection http={icode}", file=sys.stderr)
        return 1
    doc = json.loads(ibody.decode("utf-8"))
    required = (
        "duration_seconds",
        "container_format",
        "video_codec",
        "audio_codec",
        "file_size_bytes",
        "chunk_plan",
    )
    missing = [k for k in required if k not in doc]
    if missing:
        print(f"FAIL: inspection JSON missing keys {missing}", file=sys.stderr)
        return 1
    if not isinstance(doc.get("chunk_plan"), list):
        print("FAIL: chunk_plan not a list", file=sys.stderr)
        return 1
    print(
        "PASS: inspection fields ok "
        f"duration={doc.get('duration_seconds')} container={doc.get('container_format')} "
        f"v={doc.get('video_codec')} a={doc.get('audio_codec')} size={doc.get('file_size_bytes')} "
        f"chunks={len(doc['chunk_plan'])}",
    )

    if "raw_transcript" not in types:
        print("FAIL: raw_transcript missing", file=sys.stderr)
        return 1
    tr = next(o for o in outs if o.get("type") == "raw_transcript")
    tr_url = tr.get("download_url") or ""
    if not tr_url:
        print("FAIL: raw_transcript missing download_url", file=sys.stderr)
        return 1
    tcode, tbody = _get_url(tr_url, timeout=60.0)
    if tcode != 200:
        print(f"FAIL: fetch transcript http={tcode}", file=sys.stderr)
        return 1
    tdoc = json.loads(tbody.decode("utf-8"))
    for k in ("schema_version", "source", "audio_extraction", "segments"):
        if k not in tdoc:
            print(f"FAIL: transcript missing key {k}", file=sys.stderr)
            return 1
    if not isinstance(tdoc["segments"], list) or not tdoc["segments"]:
        print("FAIL: transcript segments invalid", file=sys.stderr)
        return 1
    ae = tdoc["audio_extraction"]
    if "schema_version" not in ae or "has_audio_stream" not in ae:
        print("FAIL: audio_extraction metadata incomplete", file=sys.stderr)
        return 1

    req_audio = os.environ.get("SMOKE_REQUIRE_AUDIO", "").strip().lower() in ("1", "true", "yes")
    if req_audio:
        if doc.get("audio_codec") in (None, ""):
            print(
                "FAIL: SMOKE_REQUIRE_AUDIO but media_inspection.audio_codec is null/empty",
                file=sys.stderr,
            )
            return 1
        if not ae.get("has_audio_stream"):
            print("FAIL: SMOKE_REQUIRE_AUDIO: audio_extraction.has_audio_stream must be true", file=sys.stderr)
            return 1
        if ae.get("has_audio") is not True:
            print("FAIL: SMOKE_REQUIRE_AUDIO: audio_extraction.has_audio must be true", file=sys.stderr)
            return 1
        for k in ("source_duration_seconds", "output_format", "output_bytes", "ffmpeg_command"):
            if k not in ae or ae.get(k) in (None, ""):
                print(f"FAIL: SMOKE_REQUIRE_AUDIO: audio_extraction.{k} missing or empty", file=sys.stderr)
                return 1
        if not ae.get("source_media_basename"):
            print("FAIL: SMOKE_REQUIRE_AUDIO: audio_extraction.source_media_basename missing", file=sys.stderr)
            return 1
        if not ae.get("extracted_audio_basename"):
            print(
                "FAIL: SMOKE_REQUIRE_AUDIO: audio_extraction.extracted_audio_basename missing",
                file=sys.stderr,
            )
            return 1
        allow_openai = os.environ.get("SMOKE_ALLOW_OPENAI_TRANSCRIPT", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not allow_openai and tdoc.get("source") != "transcript_stub":
            print(
                f"FAIL: expected transcript source transcript_stub, got {tdoc.get('source')!r} "
                "(set SMOKE_ALLOW_OPENAI_TRANSCRIPT=1 if worker OpenAI is intentional)",
                file=sys.stderr,
            )
            return 1
        print("PASS: SMOKE_REQUIRE_AUDIO checks ok")

    print(
        f"PASS: transcript v0 source={tdoc.get('source')} "
        f"has_audio_stream={ae.get('has_audio_stream')} has_audio={ae.get('has_audio')}",
    )

    def _assert_derived() -> int:
        for typ in ("chapters", "fact_sheet", "faqs", "metadata", "hosted_manifest"):
            c, doc = _fetch_output_json(outs, typ)
            if c != 200 or not doc:
                print(f"FAIL: could not fetch JSON for {typ} http={c}", file=sys.stderr)
                return 1
            if doc.get("derived_from") not in ("transcript_stub", "openai_whisper"):
                print(f"FAIL: {typ} missing/invalid derived_from: {doc.get('derived_from')!r}", file=sys.stderr)
                return 1
        ch_doc = _fetch_output_json(outs, "chapters")[1]
        assert ch_doc is not None
        if not ch_doc.get("chapters"):
            print("FAIL: chapters.json has empty chapters", file=sys.stderr)
            return 1
        segs = tdoc.get("segments") or []
        seg0_text = (segs[0].get("text") or "").strip()
        title0 = (ch_doc["chapters"][0].get("title") or "").strip()
        if seg0_text:
            first = (seg0_text.split() or [""])[0].lower()
            if len(first) > 1 and first not in title0.lower():
                print(
                    f"FAIL: chapter title should reflect first segment; title={title0!r} segment0={seg0_text[:80]!r}",
                    file=sys.stderr,
                )
                return 1
        hm = _fetch_output_json(outs, "hosted_manifest")[1]
        assert hm is not None
        oa = hm.get("outputs_available") or []
        if "raw_transcript" not in oa or "chapters" not in oa:
            print(f"FAIL: hosted_manifest.outputs_available incomplete: {oa!r}", file=sys.stderr)
            return 1
        if not hm.get("transcript_meta") or hm["transcript_meta"].get("source") != tdoc.get("source"):
            print("FAIL: hosted_manifest.transcript_meta.source mismatch", file=sys.stderr)
            return 1
        if not hm.get("media_meta") or hm["media_meta"].get("audio_codec") is None:
            print("FAIL: hosted_manifest.media_meta missing audio_codec", file=sys.stderr)
            return 1
        print("PASS: transcript-derived outputs (chapters, fact_sheet, faqs, metadata, hosted_manifest) validated.")
        return 0

    if _assert_derived():
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
