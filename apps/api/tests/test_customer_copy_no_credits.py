"""Customer-facing web copy must not use legacy 'credits' terminology (dashboard, upload, jobs)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WEB_APP = REPO / "apps" / "web" / "src" / "app"

FORBIDDEN = (
    "credits available",
    "processing credits",
    "credit use",
    "next credit expiry",
    "credits spent",
    "credits reserved",
)


def test_dashboard_upload_jobs_pages_avoid_credit_product_copy():
    paths = [
        WEB_APP / "dashboard" / "page.tsx",
        WEB_APP / "upload" / "page.tsx",
        WEB_APP / "jobs" / "page.tsx",
    ]
    for p in paths:
        text = p.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN:
            assert phrase not in text, f"{p.name} must not contain customer-facing phrase {phrase!r}"
