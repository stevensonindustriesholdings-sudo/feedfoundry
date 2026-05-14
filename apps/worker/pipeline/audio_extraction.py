"""FFmpeg audio extraction for transcript pipeline v0."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any

from media_inspection import run_ffprobe_json

from pipeline.errors import JobProcessingFailure

log = logging.getLogger("feedfoundry.worker.audio")


def ffprobe_has_audio_stream(path: str, *, ffprobe_binary: str | None = None) -> bool:
    doc = run_ffprobe_json(path, ffprobe_binary=ffprobe_binary)
    for stream in doc.get("streams") or []:
        if stream.get("codec_type") == "audio":
            return True
    return False


def _format_duration_seconds(ffprobe_doc: dict[str, Any]) -> float:
    fmt = ffprobe_doc.get("format") or {}
    raw = fmt.get("duration")
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def build_ffmpeg_extract_audio_command(
    input_path: str,
    output_wav_path: str,
    *,
    sample_rate_hz: int = 16000,
    channels: int = 1,
) -> list[str]:
    """Argv for mono 16 kHz PCM WAV (speech-friendly)."""
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate_hz),
        "-ac",
        str(channels),
        output_wav_path,
    ]


def run_audio_extraction(
    *,
    input_path: str,
    ffmpeg_binary: str | None = None,
    ffprobe_binary: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Extract mono 16 kHz WAV when an audio stream exists; else return (None, metadata)."""
    ff = ffmpeg_binary or os.environ.get("FFMPEG_BINARY", "ffmpeg")
    fp = ffprobe_binary or os.environ.get("FFPROBE_BINARY", "ffprobe")

    ffprobe_doc = run_ffprobe_json(input_path, ffprobe_binary=fp)
    duration = _format_duration_seconds(ffprobe_doc)
    base_meta: dict[str, Any] = {
        "schema_version": "1.0",
        "source_duration_seconds": duration,
        "has_audio_stream": False,
        "success": False,
        "ffmpeg_command": None,
        "output_format": None,
        "output_bytes": None,
        "sample_rate_hz": None,
        "channels": None,
        "error": None,
    }

    if not ffprobe_has_audio_stream(input_path, ffprobe_binary=fp):
        base_meta["success"] = True
        base_meta["skipped_reason"] = "no_audio_stream"
        base_meta["has_audio"] = False
        base_meta["source_media_basename"] = os.path.basename(input_path)
        return None, base_meta

    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="ff_audio_")
    os.close(fd)
    cmd = build_ffmpeg_extract_audio_command(input_path, out_path)
    cmd[0] = ff
    base_meta["ffmpeg_command"] = " ".join(cmd)
    base_meta["has_audio_stream"] = True

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:2000]
            base_meta["error"] = f"ffmpeg_exit_{proc.returncode}: {err}"
            base_meta["has_audio"] = False
            try:
                os.unlink(out_path)
            except OSError:
                pass
            raise JobProcessingFailure(
                "audio_extraction_failed",
                f"FFmpeg could not extract audio (exit {proc.returncode}). {err[:800] or 'No stderr.'}",
            )

        size = os.path.getsize(out_path)
        base_meta["success"] = True
        base_meta["output_format"] = "wav"
        base_meta["output_bytes"] = size
        base_meta["sample_rate_hz"] = 16000
        base_meta["channels"] = 1
        base_meta["has_audio"] = True
        base_meta["has_audio_stream"] = True
        base_meta["source_media_basename"] = os.path.basename(input_path)
        base_meta["extracted_audio_basename"] = os.path.basename(out_path)
        return out_path, base_meta
    except JobProcessingFailure:
        raise
    except Exception as exc:
        base_meta["error"] = str(exc)[:2000]
        log.exception("audio_extraction_failed")
        try:
            os.unlink(out_path)
        except OSError:
            pass
        raise JobProcessingFailure(
            "audio_extraction_failed",
            f"Audio extraction raised an unexpected error: {type(exc).__name__}",
        ) from exc
