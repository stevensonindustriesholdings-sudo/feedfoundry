#!/usr/bin/env python3
"""
Batch real-media smoke: every ``*.mp4`` in a folder through presign → PUT → job → poll → validate.

Environment (same auth as ``smoke_real_media_upload.py``):
  SMOKE_BASE_URL or BASE_URL
  SMOKE_INTERNAL_KEY
  SMOKE_ORG_ID (default org_dev_demo)
  SAMPLE_PACK_DIR — folder containing .mp4 files (or pass directory as argv[1])

Optional:
  SAMPLE_PACK_REPORT — path to markdown report (default: ``sample-pack-report.md`` in cwd)
  SAMPLE_PACK_MAX_FILES — max MP4s to process (default 20)
  SAMPLE_PACK_ONLY — optional comma-separated basenames (e.g. ``04_hd_h264_aac.mp4``) to process a subset
  SMOKE_POLL_SECONDS, SMOKE_JOB_TIMEOUT_SECONDS
  SAMPLE_PACK_REQUIRE_AUDIO=1 — same strict audio checks as SMOKE_REQUIRE_AUDIO=1 on single smoke
  SMOKE_ALLOW_OPENAI_TRANSCRIPT=1 — allow transcript source other than transcript_stub when validating

Continues after per-file failures; exit code 1 if any file ended with validation/job failure.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PackRow:
    filename: str = ""
    size_bytes: int = 0
    duration_seconds: str = ""
    audio_codec: str = ""
    video_codec: str = ""
    job_id: str = ""
    status: str = ""
    output_count: int = 0
    validation_error: str = ""
    media_asset_id: str = ""


def _load_smoke_module():
    root = Path(__file__).resolve().parent
    path = root / "smoke_real_media_upload.py"
    spec = importlib.util.spec_from_file_location("smoke_real_media_upload", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load smoke_real_media_upload.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _validate_pack(
    *,
    outs: list[dict[str, Any]],
    require_audio: bool,
    allow_openai: bool,
    smoke: Any,
) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Return (error, inspection_doc, transcript_doc) or (None, doc, tdoc) on success."""
    types = [o.get("type") for o in outs]
    if len(types) != 7:
        return f"expected 7 outputs, got {len(types)}: {types}", None, None
    if "media_inspection" not in types:
        return "media_inspection missing", None, None
    icode, doc = smoke._fetch_output_json(outs, "media_inspection")
    if icode != 200 or not doc:
        return f"media_inspection fetch http={icode}", None, None
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
        return f"inspection missing keys {missing}", None, None
    if not isinstance(doc.get("chunk_plan"), list):
        return "chunk_plan not a list", None, None

    if "raw_transcript" not in types:
        return "raw_transcript missing", None, None
    tcode, tdoc = smoke._fetch_output_json(outs, "raw_transcript")
    if tcode != 200 or not tdoc:
        return f"raw_transcript fetch http={tcode}", None, None
    for k in ("schema_version", "source", "audio_extraction", "segments"):
        if k not in tdoc:
            return f"transcript missing key {k}", None, None
    if not isinstance(tdoc["segments"], list) or not tdoc["segments"]:
        return "transcript segments invalid", None, None
    ae = tdoc["audio_extraction"]
    if "schema_version" not in ae or "has_audio_stream" not in ae:
        return "audio_extraction incomplete", None, None

    if require_audio:
        if doc.get("audio_codec") in (None, ""):
            return "REQUIRE_AUDIO: media_inspection.audio_codec empty", None, None
        if not ae.get("has_audio_stream"):
            return "REQUIRE_AUDIO: has_audio_stream false", None, None
        if ae.get("has_audio") is not True:
            return "REQUIRE_AUDIO: has_audio not true", None, None
        for k in ("source_duration_seconds", "output_format", "output_bytes", "ffmpeg_command"):
            if k not in ae or ae.get(k) in (None, ""):
                return f"REQUIRE_AUDIO: audio_extraction.{k} missing", None, None
        if not ae.get("source_media_basename"):
            return "REQUIRE_AUDIO: source_media_basename missing", None, None
        if not ae.get("extracted_audio_basename"):
            return "REQUIRE_AUDIO: extracted_audio_basename missing", None, None
        if not allow_openai and tdoc.get("source") != "transcript_stub":
            return f"expected transcript_stub source, got {tdoc.get('source')!r}", None, None

    for typ in ("chapters", "fact_sheet", "faqs", "metadata", "hosted_manifest"):
        c, d = smoke._fetch_output_json(outs, typ)
        if c != 200 or not d:
            return f"fetch {typ} http={c}", doc, tdoc
        if d.get("derived_from") not in ("transcript_stub", "openai_whisper"):
            return f"{typ} derived_from invalid: {d.get('derived_from')!r}", doc, tdoc
    _, ch_doc = smoke._fetch_output_json(outs, "chapters")
    if not ch_doc or not ch_doc.get("chapters"):
        return "chapters empty", doc, tdoc
    segs = tdoc.get("segments") or []
    seg0_text = (segs[0].get("text") or "").strip()
    title0 = (ch_doc["chapters"][0].get("title") or "").strip()
    if seg0_text:
        first = (seg0_text.split() or [""])[0].lower()
        if len(first) > 1 and first not in title0.lower():
            return "chapter title does not reflect first segment", doc, tdoc
    _, hm = smoke._fetch_output_json(outs, "hosted_manifest")
    if not hm:
        return "hosted_manifest missing", doc, tdoc
    oa = hm.get("outputs_available") or []
    if "raw_transcript" not in oa or "chapters" not in oa:
        return f"outputs_available incomplete: {oa!r}", doc, tdoc
    if not hm.get("transcript_meta") or hm["transcript_meta"].get("source") != tdoc.get("source"):
        return "hosted_manifest.transcript_meta.source mismatch", doc, tdoc
    if not hm.get("media_meta"):
        return "hosted_manifest.media_meta missing", doc, tdoc
    if require_audio and hm["media_meta"].get("audio_codec") in (None, ""):
        return "hosted_manifest.media_meta.audio_codec missing (required)", doc, tdoc

    return None, doc, tdoc


def _process_one(
    *,
    mp4: Path,
    base: str,
    auth: dict[str, str],
    smoke: Any,
    poll_s: float,
    timeout_s: float,
    require_audio: bool,
    allow_openai: bool,
) -> PackRow:
    row = PackRow(filename=mp4.name, size_bytes=mp4.stat().st_size)
    body = mp4.read_bytes()
    content_type = "video/mp4"

    code, raw = smoke._post_json(
        base,
        "/v1/uploads/presign",
        {
            "filename": mp4.name,
            "content_type": content_type,
            "file_size_bytes": len(body),
            "media_type": "video",
        },
        auth,
    )
    if code != 200:
        row.validation_error = f"presign http={code} {raw[:200]!r}"
        return row

    pres = json.loads(raw.decode("utf-8"))
    row.media_asset_id = str(pres.get("media_asset_id", ""))
    put_code, put_err = smoke._put_bytes(pres["upload_url"], body, content_type)
    if put_code < 200 or put_code >= 300:
        row.validation_error = f"PUT http={put_code} {put_err}"
        return row

    jcode, jraw = smoke._post_json(
        base,
        "/v1/jobs",
        {"media_asset_id": pres["media_asset_id"], "requested_outputs": ["transcript"]},
        auth,
    )
    if jcode != 200:
        row.validation_error = f"POST jobs http={jcode} {jraw[:200]!r}"
        return row

    job_id = json.loads(jraw.decode("utf-8"))["job_id"]
    row.job_id = job_id

    deadline = time.monotonic() + timeout_s
    status = ""
    while time.monotonic() < deadline:
        scode, sbody = smoke._get(base, f"/v1/jobs/{job_id}", auth)
        if scode != 200:
            row.validation_error = f"GET job http={scode}"
            row.status = status or "unknown"
            return row
        info = json.loads(sbody.decode("utf-8"))
        status = info.get("status", "")
        row.status = status
        if status in ("complete", "failed", "cancelled"):
            break
        time.sleep(poll_s)

    if status != "complete":
        row.validation_error = f"job not complete (status={status})"
        return row

    ocode, obody = smoke._get(base, f"/v1/jobs/{job_id}/outputs", auth)
    if ocode != 200:
        row.validation_error = f"GET outputs http={ocode}"
        return row

    outs = json.loads(obody.decode("utf-8")).get("outputs", [])
    row.output_count = len(outs)

    err, doc, _tdoc = _validate_pack(outs=outs, require_audio=require_audio, allow_openai=allow_openai, smoke=smoke)
    if err:
        row.validation_error = err
    if doc:
        row.duration_seconds = str(doc.get("duration_seconds", ""))
        row.audio_codec = str(doc.get("audio_codec") or "")
        row.video_codec = str(doc.get("video_codec") or "")
    return row


def main() -> int:
    base = (os.environ.get("SMOKE_BASE_URL") or os.environ.get("BASE_URL") or "").strip()
    key = (os.environ.get("SMOKE_INTERNAL_KEY") or "").strip()
    org = (os.environ.get("SMOKE_ORG_ID") or "org_dev_demo").strip()
    pack_dir = (os.environ.get("SAMPLE_PACK_DIR") or (sys.argv[1] if len(sys.argv) > 1 else "")).strip()
    report_path = Path(os.environ.get("SAMPLE_PACK_REPORT") or "sample-pack-report.md").resolve()
    max_files = int(os.environ.get("SAMPLE_PACK_MAX_FILES", "20"))

    if not base or not key or not pack_dir:
        print(
            "Set SMOKE_BASE_URL, SMOKE_INTERNAL_KEY, and SAMPLE_PACK_DIR (or pass directory as argv[1]).",
            file=sys.stderr,
        )
        return 2

    root = Path(pack_dir)
    if not root.is_dir():
        print(f"Not a directory: {pack_dir}", file=sys.stderr)
        return 2

    mp4s = sorted(root.glob("*.mp4"))[:max_files]
    if not mp4s:
        print(f"No .mp4 files under {root}", file=sys.stderr)
        return 2

    only = os.environ.get("SAMPLE_PACK_ONLY", "").strip()
    if only:
        allow = {n.strip() for n in only.split(",") if n.strip()}
        mp4s = [p for p in mp4s if p.name in allow]
        if not mp4s:
            print(f"No files match SAMPLE_PACK_ONLY={only!r}", file=sys.stderr)
            return 2

    smoke = _load_smoke_module()
    auth = {"Authorization": f"Bearer {key}", "X-Org-Id": org}
    poll_s = float(os.environ.get("SMOKE_POLL_SECONDS", "5"))
    timeout_s = float(os.environ.get("SMOKE_JOB_TIMEOUT_SECONDS", "600"))
    require_audio = os.environ.get("SAMPLE_PACK_REQUIRE_AUDIO", os.environ.get("SMOKE_REQUIRE_AUDIO", "1")).strip().lower() in (
        "1",
        "true",
        "yes",
    )
    allow_openai = os.environ.get("SMOKE_ALLOW_OPENAI_TRANSCRIPT", "").strip().lower() in ("1", "true", "yes")

    rows: list[PackRow] = []
    failures = 0
    for mp4 in mp4s:
        print(f"\n>>> {mp4.name} ({mp4.stat().st_size} bytes)", flush=True)
        try:
            row = _process_one(
                mp4=mp4,
                base=base,
                auth=auth,
                smoke=smoke,
                poll_s=poll_s,
                timeout_s=timeout_s,
                require_audio=require_audio,
                allow_openai=allow_openai,
            )
        except Exception as exc:
            row = PackRow(filename=mp4.name, size_bytes=mp4.stat().st_size, validation_error=f"exception:{exc}")
        if row.validation_error:
            failures += 1
            print(f"FAIL {mp4.name}: {row.validation_error}", flush=True)
        else:
            print(
                f"OK {mp4.name} job={row.job_id} duration={row.duration_seconds}s "
                f"v={row.video_codec} a={row.audio_codec}",
                flush=True,
            )
        rows.append(row)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# FeedFoundry sample pack batch report",
        "",
        f"- Generated: `{ts}` (UTC)",
        f"- Directory: `{root}`",
        f"- Files attempted: **{len(rows)}**",
        f"- Failures: **{failures}**",
        f"- `SAMPLE_PACK_REQUIRE_AUDIO`: `{require_audio}`",
        "",
        "| filename | size_bytes | duration_s | video_codec | audio_codec | job_id | status | outputs | error |",
        "|---|---:|---|---|---|---|---:|---|---|",
    ]
    for r in rows:
        err = (r.validation_error or "").replace("|", "\\|").replace("\n", " ")[:400]
        lines.append(
            f"| {r.filename} | {r.size_bytes} | {r.duration_seconds} | {r.video_codec} | {r.audio_codec} | "
            f"`{r.job_id}` | {r.status} | {r.output_count} | {err} |"
        )
    lines.extend(
        [
            "",
            "## Codec / shape notes",
            "",
            "Use the **video_codec** / **audio_codec** columns and **error** to see which containers "
            "passed strict audio + derived-output validation.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    csv_path = report_path.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "size_bytes",
                "duration_seconds",
                "video_codec",
                "audio_codec",
                "job_id",
                "status",
                "output_count",
                "validation_error",
                "media_asset_id",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "filename": r.filename,
                    "size_bytes": r.size_bytes,
                    "duration_seconds": r.duration_seconds,
                    "video_codec": r.video_codec,
                    "audio_codec": r.audio_codec,
                    "job_id": r.job_id,
                    "status": r.status,
                    "output_count": r.output_count,
                    "validation_error": r.validation_error,
                    "media_asset_id": r.media_asset_id,
                }
            )

    print(f"\nWrote {report_path} and {csv_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
