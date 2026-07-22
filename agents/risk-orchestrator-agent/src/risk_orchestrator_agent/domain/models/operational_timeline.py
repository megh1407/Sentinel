"""OperationalTimeline value object (Phase 2.2 §9).

A bounded sliding window (default 60 minutes, configurable per domain) of
ordered TimelineEntry records per zone. Deliberately NOT the same as the
full historical record in PostgreSQL (`HistoricalContext`) — a fast,
Redis-backed, working-memory-scale window sized for trend detection, not
audit (Phase 2.2 §9.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    domain: str
    field: str
    value: str
    analyzed_at: datetime
    event_id: str


@dataclass(frozen=True, slots=True)
class OperationalTimeline:
    entries: tuple[TimelineEntry, ...] = field(default_factory=tuple)
    window: timedelta = timedelta(minutes=60)

    def with_entry(self, entry: TimelineEntry, *, now: datetime) -> "OperationalTimeline":
        """Insert `entry` at its correct temporal position by `analyzed_at`
        (Phase 2.2 §9.4) — never appended by arrival order — then trim
        anything older than `window` relative to `now`."""
        merged = list(self.entries) + [entry]
        merged.sort(key=lambda e: e.analyzed_at)
        cutoff = now - self.window
        trimmed = tuple(e for e in merged if e.analyzed_at >= cutoff)
        return OperationalTimeline(entries=trimmed, window=self.window)

    def for_domain(self, domain: str) -> tuple[TimelineEntry, ...]:
        return tuple(e for e in self.entries if e.domain == domain)

    def is_monotonically_increasing(self, domain: str, field_name: str) -> bool:
        """Lightweight structural trend computation (Phase 2.2 §9.4) —
        does not itself decide whether a trend is *risky*."""
        values: list[float] = []
        for e in self.entries:
            if e.domain == domain and e.field == field_name:
                try:
                    values.append(float(e.value))
                except ValueError:
                    continue
        return len(values) >= 2 and all(b >= a for a, b in zip(values, values[1:]))
