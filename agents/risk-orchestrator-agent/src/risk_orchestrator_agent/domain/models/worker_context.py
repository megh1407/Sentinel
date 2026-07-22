"""WorkerContext value object (Phase 2.2 §4.1, §4.2).

Point-in-time domain snapshot. Structural equality (Phase 2.2 §4.2).
Two snapshots with identical values are interchangeable — this is what
distinguishes it from the `Worker` reference Entity (Phase 2.5 §4.1),
whose identity persists across snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class ProximityAlert:
    hazard_type: str
    distance_m: float
    safe_distance_m: float

    @property
    def within_hazard_radius(self) -> bool:
        return self.distance_m < self.safe_distance_m


@dataclass(frozen=True, slots=True)
class WorkerContext:
    worker_id: str
    safety_status: str
    ppe_compliance: float | None
    ppe_violations: tuple[str, ...]
    zone_clearance: bool | None
    proximity_alerts: tuple[ProximityAlert, ...]
    confidence: ConfidenceScore
    analyzed_at: datetime
    age: Age
    stale: bool = False
