from __future__ import annotations

from media_inspection import build_media_inspection_payload


def test_build_media_inspection_payload_extracts_codecs_and_chunks():
    doc = {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "12.5",
        },
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    out = build_media_inspection_payload(doc, file_size_bytes=999)
    assert out["schema_version"] == "1.0"
    assert out["duration_seconds"] == 12.5
    assert out["container_format"] == "mov,mp4,m4a,3gp,3g2,mj2"
    assert out["video_codec"] == "h264"
    assert out["audio_codec"] == "aac"
    assert out["file_size_bytes"] == 999
    assert len(out["chunk_plan"]) >= 1
    assert out["chunk_plan"][0]["index"] == 0
    assert out["chunk_plan"][0]["start_sec"] == 0.0
    assert out["chunk_plan"][0]["end_sec"] == 12.5
