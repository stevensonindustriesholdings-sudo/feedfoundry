from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pipeline.audio_extraction import run_audio_extraction
from pipeline.errors import JobProcessingFailure


@patch("pipeline.audio_extraction.ffprobe_has_audio_stream", return_value=True)
@patch("pipeline.audio_extraction.run_ffprobe_json")
@patch("subprocess.run")
def test_run_audio_extraction_raises_on_ffmpeg_nonzero(
    mock_run: MagicMock,
    mock_ffprobe: MagicMock,
    _mock_has_audio: MagicMock,
) -> None:
    mock_ffprobe.return_value = {
        "format": {"duration": "5.0"},
        "streams": [{"codec_type": "audio", "codec_name": "aac"}],
    }
    mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg: broken pipe", stdout="")
    with pytest.raises(JobProcessingFailure) as excinfo:
        run_audio_extraction(input_path="/tmp/fake_input.mp4", ffmpeg_binary="ffmpeg", ffprobe_binary="ffprobe")
    assert excinfo.value.code == "audio_extraction_failed"
    assert "FFmpeg" in excinfo.value.message
