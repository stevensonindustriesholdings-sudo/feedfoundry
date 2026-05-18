"""Rule-based FFmpeg failure triage — policy signal only (no ledger side effects)."""

from __future__ import annotations

from ai.feedfoundry_agents.schemas import FFmpegFailureClassification, FFmpegFailureInput


def classify_ffmpeg_failure(sample: FFmpegFailureInput) -> FFmpegFailureClassification:
    """Return ``debit_processing_minutes: false`` for all failure classes (explicit contract)."""
    stderr = (sample.stderr_snippet or "").lower()
    rc = int(sample.return_code)

    family = "unknown"
    hint = "Inspect full stderr and command; retry with a known-good sample."
    conf = 0.35

    if "invalid data found when processing input" in stderr or "invalid argument" in stderr:
        family = "demux_decode"
        hint = "Re-encode or remux source; confirm container/codec supported by FFmpeg build."
        conf = 0.78
    elif "broken pipe" in stderr or rc == 141:
        family = "io_pipe"
        hint = "Upstream writer closed pipe; check disk space and concurrent readers."
        conf = 0.72
    elif "no such file" in stderr or "could not find" in stderr:
        family = "missing_input"
        hint = "Verify local path or completed download before invoking FFmpeg."
        conf = 0.9
    elif "permission denied" in stderr:
        family = "permissions"
        hint = "Check filesystem permissions for input/output paths."
        conf = 0.85

    return FFmpegFailureClassification(
        failure_family=family,
        confidence_0_1=conf,
        debit_processing_minutes=False,
        remediation_hint=hint,
    )
