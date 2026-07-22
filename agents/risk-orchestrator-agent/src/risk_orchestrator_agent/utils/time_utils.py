"""Small, dependency-free shared time helpers (Phase 3.1 §2's `utils/`
package — staleness/age computation, Phase 2.2 §4.2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_age(analyzed_at: datetime, *, now: datetime | None = None) -> timedelta:
    reference = now or utcnow()
    if analyzed_at.tzinfo is None:
        analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)
    return reference - analyzed_at


def is_stale(analyzed_at: datetime, threshold: timedelta, *, now: datetime | None = None) -> bool:
    return compute_age(analyzed_at, now=now) > threshold
