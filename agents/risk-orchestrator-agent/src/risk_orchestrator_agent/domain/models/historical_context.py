"""HistoricalContext value object (Phase 2.2 §4.1, §4.2, §7).

Sourced from PostgreSQL via HistoryRepositoryPort, not a live agent
topic. `recent_transitions` is the trajectory, not just the current
point — feeds DecisionEngine's risk-level-change detection in a later
implementation phase; this phase only assembles it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SeverityTransition:
    from_severity: str | None
    to_severity: str
    transitioned_at: datetime


@dataclass(frozen=True, slots=True)
class HistoricalContext:
    previous_severity: str | None
    previous_computed_at: datetime | None
    recent_transitions: tuple[SeverityTransition, ...] = field(default_factory=tuple)
