from __future__ import annotations

from pipeline.audio_extraction import build_ffmpeg_extract_audio_command


def test_build_ffmpeg_extract_audio_command_shape():
    cmd = build_ffmpeg_extract_audio_command("/tmp/in.mp4", "/tmp/out.wav", sample_rate_hz=16000, channels=1)
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd
    idx = cmd.index("-i")
    assert cmd[idx + 1] == "/tmp/in.mp4"
    assert "-vn" in cmd
    assert "pcm_s16le" in cmd
    assert "-ar" in cmd
    assert "16000" in cmd
    assert "-ac" in cmd
    assert "1" in cmd
    assert cmd[-1] == "/tmp/out.wav"
