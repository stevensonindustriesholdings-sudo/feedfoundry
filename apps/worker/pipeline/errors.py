"""Structured worker pipeline failures (safe for job failure_reason / API)."""

from __future__ import annotations


class JobProcessingFailure(Exception):
    """Raised when a job must fail without charging reserved processing minutes."""

    __slots__ = ("code", "message")

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
