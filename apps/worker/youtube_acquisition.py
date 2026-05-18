"""YouTube source acquisition (worker-side).

Live acquisition is gated by ``FF_YOUTUBE_SOURCE_ACQUISITION_LIVE=1``. The adapter
uses library dependencies (yt-dlp and optionally youtube-transcript-api), not a
random globally installed shell command. It only targets public URLs submitted by
API validation; private/login/DRM failures are returned as structured acquisition
errors for the worker to persist on the queue/job.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([a-zA-Z0-9_-]{11})")


@dataclass
class YouTubeAcquisitionResult:
    local_media_path: str | None
    filename: str
    content_type: str = "video/mp4"
    title: str | None = None
    duration_seconds: float | None = None
    transcript_payload: dict[str, Any] | None = None
    media_acquired: bool = True
    nonfatal_error: str | None = None


class YouTubeAcquisitionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def youtube_source_acquisition_live_enabled() -> bool:
    return os.environ.get("FF_YOUTUBE_SOURCE_ACQUISITION_LIVE", "").strip().lower() in ("1", "true", "yes")


def _video_id_from_url(url: str) -> str | None:
    stripped = (url or "").strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", stripped):
        return stripped
    m = _VIDEO_ID_RE.search(stripped)
    return m.group(1) if m else None


def _fetch_public_transcript(youtube_url: str) -> dict[str, Any] | None:
    """Best-effort public caption transcript. Absence is not fatal to media acquisition."""
    video_id = _video_id_from_url(youtube_url)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception:
        return None

    try:
        api = YouTubeTranscriptApi()
        try:
            rows = api.fetch(video_id, languages=["en"])
        except TypeError:
            # Older youtube-transcript-api exposed fetch/list methods as class/static methods.
            rows = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
    except Exception:
        try:
            rows = YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
        except Exception:
            return None

    segments: list[dict[str, Any]] = []
    for row in rows:
        # FetchedTranscriptSnippet exposes attrs; older API returns dicts.
        if isinstance(row, dict):
            text = str(row.get("text") or "").strip()
            start = float(row.get("start") or 0.0)
            duration = float(row.get("duration") or 0.0)
        else:
            text = str(getattr(row, "text", "") or "").strip()
            start = float(getattr(row, "start", 0.0) or 0.0)
            duration = float(getattr(row, "duration", 0.0) or 0.0)
        if not text:
            continue
        segments.append({"start": start, "end": start + max(duration, 0.0), "text": text})
    if not segments:
        return None
    return {
        "schema_version": "1.0",
        "source": "youtube_transcript",
        "segments": segments,
    }


def _yt_dlp_options(outtmpl: str) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "format": os.environ.get("FF_YOUTUBE_DLP_FORMAT", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"),
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": float(os.environ.get("FF_YOUTUBE_DLP_SOCKET_TIMEOUT_SECONDS", "30")),
        "http_headers": {
            "User-Agent": os.environ.get(
                "FF_YOUTUBE_DLP_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            ),
            "Accept-Language": os.environ.get("FF_YOUTUBE_DLP_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
        },
    }
    clients = [c.strip() for c in os.environ.get("FF_YOUTUBE_DLP_PLAYER_CLIENTS", "android,web").split(",") if c.strip()]
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
    max_bytes = int(os.environ.get("FF_YOUTUBE_MAX_DOWNLOAD_BYTES", "536870912"))
    if max_bytes > 0:
        opts["max_filesize"] = max_bytes
    return opts


def acquire_youtube_source(*, youtube_url: str, work_dir: str) -> YouTubeAcquisitionResult:
    """Download a public YouTube source file and optionally public captions.

    Returns a local file path owned by the caller. Raises YouTubeAcquisitionError
    with a stable code/message for worker queue/job reporting.
    """
    if not youtube_source_acquisition_live_enabled():
        raise YouTubeAcquisitionError("youtube_live_acquisition_disabled", "Live YouTube acquisition is disabled.")

    try:
        from yt_dlp import YoutubeDL  # type: ignore
        from yt_dlp.utils import DownloadError  # type: ignore
    except Exception as exc:
        raise YouTubeAcquisitionError(
            "youtube_acquisition_dependency_missing",
            "yt-dlp dependency is not installed in the worker image.",
        ) from exc

    wd = Path(work_dir)
    wd.mkdir(parents=True, exist_ok=True)
    outtmpl = str(wd / "youtube_source.%(ext)s")
    opts = _yt_dlp_options(outtmpl)

    title = "YouTube source"
    duration = None
    transcript_payload = _fetch_public_transcript(youtube_url)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            local_path = None
            requested = info.get("requested_downloads") if isinstance(info, dict) else None
            if requested:
                local_path = requested[0].get("filepath") or requested[0].get("filename")
            if not local_path:
                local_path = ydl.prepare_filename(info)
                if local_path and not os.path.exists(local_path) and not local_path.endswith(".mp4"):
                    mp4_candidate = str(Path(local_path).with_suffix(".mp4"))
                    if os.path.exists(mp4_candidate):
                        local_path = mp4_candidate
            if not local_path or not os.path.exists(local_path):
                candidates = sorted(wd.glob("youtube_source.*"), key=lambda p: p.stat().st_mtime, reverse=True)
                local_path = str(candidates[0]) if candidates else None
            if not local_path or not os.path.exists(local_path):
                raise YouTubeAcquisitionError("youtube_download_missing_file", "yt-dlp completed without a staged media file.")
            title = str(info.get("title") or "YouTube source") if isinstance(info, dict) else "YouTube source"
            if isinstance(info, dict) and info.get("duration") is not None:
                try:
                    duration = float(info["duration"])
                except (TypeError, ValueError):
                    duration = None
    except YouTubeAcquisitionError as exc:
        if transcript_payload:
            return YouTubeAcquisitionResult(
                local_media_path=None,
                filename="youtube_transcript.json",
                content_type="application/json",
                title=title,
                duration_seconds=duration,
                transcript_payload=transcript_payload,
                media_acquired=False,
                nonfatal_error=exc.message[:1000],
            )
        raise
    except DownloadError as exc:
        msg = str(exc)[:1000]
        if transcript_payload:
            return YouTubeAcquisitionResult(
                local_media_path=None,
                filename="youtube_transcript.json",
                content_type="application/json",
                title=title,
                duration_seconds=duration,
                transcript_payload=transcript_payload,
                media_acquired=False,
                nonfatal_error=msg,
            )
        raise YouTubeAcquisitionError("youtube_download_failed", msg) from exc
    except Exception as exc:
        msg = str(exc)[:1000]
        if transcript_payload:
            return YouTubeAcquisitionResult(
                local_media_path=None,
                filename="youtube_transcript.json",
                content_type="application/json",
                title=title,
                duration_seconds=duration,
                transcript_payload=transcript_payload,
                media_acquired=False,
                nonfatal_error=msg,
            )
        raise YouTubeAcquisitionError("youtube_acquisition_failed", msg) from exc

    filename = Path(local_path).name or "youtube_source.mp4"
    return YouTubeAcquisitionResult(
        local_media_path=local_path,
        filename=filename,
        content_type="video/mp4" if filename.lower().endswith(".mp4") else "application/octet-stream",
        title=title,
        duration_seconds=duration,
        transcript_payload=transcript_payload,
        media_acquired=True,
    )
