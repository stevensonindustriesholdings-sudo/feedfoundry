from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from pipeline.chunk_plan import plan_chunks
from pipeline.errors import JobProcessingFailure


def run_ffprobe_json(path: str, *, ffprobe_binary: str | None = None) -> dict[str, Any]:
    binary = ffprobe_binary or os.environ.get("FFPROBE_BINARY", "ffprobe")
    proc = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:1500]
        raise JobProcessingFailure(
            "ffprobe_failed",
            f"Media probe failed (exit {proc.returncode}). {err or 'No stderr from ffprobe.'}",
        )
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise JobProcessingFailure(
            "ffprobe_invalid_json",
            "ffprobe returned data that could not be parsed as JSON.",
        ) from exc


def inspect_media_file(path: str, *, ffprobe_binary: str | None = None) -> dict[str, Any]:
    """Run ffprobe + size; return media_inspection.json payload."""
    size = os.path.getsize(path)
    raw = run_ffprobe_json(path, ffprobe_binary=ffprobe_binary)
    return build_media_inspection_payload(raw, file_size_bytes=size)


def build_media_inspection_payload(ffprobe_doc: dict[str, Any], *, file_size_bytes: int) -> dict[str, Any]:
    fmt = ffprobe_doc.get("format") or {}
    duration_raw = fmt.get("duration")
    try:
        duration_seconds = float(duration_raw) if duration_raw is not None else 0.0
    except (TypeError, ValueError):
        duration_seconds = 0.0

    video_codec: str | None = None
    audio_codec: str | None = None
    for stream in ffprobe_doc.get("streams") or []:
        if stream.get("codec_type") == "video" and video_codec is None:
            video_codec = stream.get("codec_name")
        if stream.get("codec_type") == "audio" and audio_codec is None:
            audio_codec = stream.get("codec_name")

    chunks = plan_chunks(duration_seconds)
    chunk_plan = [{"index": c.index, "start_sec": c.start_sec, "end_sec": c.end_sec} for c in chunks]

    return {
        "schema_version": "1.0",
        "duration_seconds": duration_seconds,
        "container_format": fmt.get("format_name"),
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "file_size_bytes": file_size_bytes,
        "chunk_plan": chunk_plan,
    }
