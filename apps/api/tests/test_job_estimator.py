from pathlib import Path

from app.services.job_estimator import estimate_job_credits


def test_estimate_positive():
    root = Path(__file__).resolve().parents[3]
    est = estimate_job_credits(
        routing_path=root / "ai-routing.yaml",
        requested_outputs=["transcript", "metadata", "fact_sheet"],
        media_duration_seconds=3600,
    )
    assert est >= 1
