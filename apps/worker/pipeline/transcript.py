"""Transcript pipeline v0 — interface, stub provider, optional OpenAI Whisper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger("feedfoundry.worker.transcript")


@dataclass
class TranscriptPipelineInput:
    job_id: str
    media_asset_id: str
    audio_wav_path: str | None
    audio_extraction: dict[str, Any]
    media_inspection: dict[str, Any] | None


class TranscriptProvider(Protocol):
    """Pluggable ASR / transcript source."""

    name: str

    def transcribe(self, inp: TranscriptPipelineInput) -> dict[str, Any]:
        ...


def _duration_for_stub(inp: TranscriptPipelineInput) -> float:
    ext = inp.audio_extraction or {}
    if ext.get("source_duration_seconds") is not None:
        try:
            return max(0.5, float(ext["source_duration_seconds"]))
        except (TypeError, ValueError):
            pass
    mi = inp.media_inspection or {}
    if mi.get("duration_seconds") is not None:
        try:
            return max(0.5, float(mi["duration_seconds"]))
        except (TypeError, ValueError):
            pass
    return 1.0


def build_transcript_stub_payload(inp: TranscriptPipelineInput, *, source: str) -> dict[str, Any]:
    duration = _duration_for_stub(inp)
    return {
        "schema_version": "1.0",
        "source": source,
        "audio_extraction": dict(inp.audio_extraction),
        "segments": [
            {
                "start": 0.0,
                "end": duration,
                "text": (
                    f"transcript_stub_v0 job={inp.job_id} media={inp.media_asset_id} "
                    f"(no external ASR configured or audio missing)"
                ),
            }
        ],
    }


def _openai_configured(api_key: str) -> bool:
    k = (api_key or "").strip()
    if not k or k.lower() in ("replace_me", ""):
        return False
    return True


class OpenAIWhisperTranscriptProvider:
    name = "openai_whisper"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip()

    def transcribe(self, inp: TranscriptPipelineInput) -> dict[str, Any]:
        if not inp.audio_wav_path or not inp.audio_extraction.get("success"):
            return build_transcript_stub_payload(inp, source="openai_whisper_skipped_no_audio")

        url = "https://api.openai.com/v1/audio/transcriptions"
        import httpx

        try:
            with open(inp.audio_wav_path, "rb") as audio_fp:
                wav_bytes = audio_fp.read()
            with httpx.Client(timeout=600.0) as client:
                files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
                data = {"model": "whisper-1", "response_format": "verbose_json"}
                r = client.post(
                    url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files=files,
                )
            if r.status_code >= 400:
                log.warning("openai_whisper_http_%s body=%s", r.status_code, r.text[:500])
                out = build_transcript_stub_payload(inp, source="openai_whisper_fallback")
                out["provider_error"] = f"http_{r.status_code}"
                return out
            body = r.json()
        except Exception as exc:
            log.exception("openai_whisper_request_failed")
            out = build_transcript_stub_payload(inp, source="openai_whisper_fallback")
            out["provider_error"] = str(exc)[:500]
            return out

        segments_out: list[dict[str, Any]] = []
        for seg in body.get("segments") or []:
            try:
                segments_out.append(
                    {
                        "start": float(seg.get("start", 0.0)),
                        "end": float(seg.get("end", 0.0)),
                        "text": (seg.get("text") or "").strip(),
                    }
                )
            except (TypeError, ValueError):
                continue
        if not segments_out and body.get("text"):
            segments_out.append(
                {"start": 0.0, "end": _duration_for_stub(inp), "text": str(body["text"]).strip()}
            )
        if not segments_out:
            return build_transcript_stub_payload(inp, source="openai_whisper_fallback_empty")

        return {
            "schema_version": "1.0",
            "source": "openai_whisper",
            "audio_extraction": dict(inp.audio_extraction),
            "segments": segments_out,
        }


class StubTranscriptProvider:
    name = "transcript_stub"

    def transcribe(self, inp: TranscriptPipelineInput) -> dict[str, Any]:
        return build_transcript_stub_payload(inp, source="transcript_stub")


def select_transcript_provider(*, openai_api_key: str) -> TranscriptProvider:
    if _openai_configured(openai_api_key):
        return OpenAIWhisperTranscriptProvider(openai_api_key)
    return StubTranscriptProvider()


def run_transcript_pipeline_v0(
    inp: TranscriptPipelineInput,
    *,
    openai_api_key: str,
) -> dict[str, Any]:
    provider = select_transcript_provider(openai_api_key=openai_api_key)
    log.info("transcript_provider job_id=%s provider=%s", inp.job_id, provider.name)
    return provider.transcribe(inp)
