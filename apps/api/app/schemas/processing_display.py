"""Customer-facing labels for internal ledger integers (wallet + job estimates).

Internal persistence still uses ``*_credits`` column names; API responses expose
**processing minutes** (same numeric unit, product vocabulary only).
"""

from __future__ import annotations


def ledger_units_as_processing_minutes(amount: int | None) -> int | None:
    if amount is None:
        return None
    return int(amount)


def processing_minutes_to_approx_hours(minutes: int | None) -> float | None:
    if minutes is None:
        return None
    return round(float(minutes) / 60.0, 4)
