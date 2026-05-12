from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def extract_audio_wav(
    source_path: str,
    dest_wav_path: str,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> bool:
    try:
        subprocess.run(
            [
                ffmpeg_binary,
                "-y",
                "-i",
                source_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                dest_wav_path,
            ],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        log.error("ffmpeg_extract_failed %s", e)
        return False
