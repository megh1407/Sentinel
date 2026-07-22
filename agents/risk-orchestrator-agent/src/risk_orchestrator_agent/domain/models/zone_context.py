"""ZoneContext value object (Phase 2.2 §4.1, §4.2).

Note: FRS §4.1 classifies `zone_context.py` alongside `risk_context.py` as
holding an Entity in addition to this module's Value Object snapshot —
the `Zone` reference Entity (Phase 2.5 §4.1) is intentionally not modeled
here since its full lifecycle belongs to Zone Intelligence Agent's own
bounded context (Phase 2.5 §1.7); this module holds only the point-in-time
snapshot ContextBuilder assembles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class Anomaly:
    anomaly_type: str
    description: str
    severity: str
    sensor_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ZoneContext:
    zone_id: str
    site_id: str
    zone_state: str
    risk_factors: tuple[str, ...]
    anomalies: tuple[Anomaly, ...]
    worker_count: int | None
    equipment_ids: tuple[str, ...]
    confidence: ConfidenceScore
    analyzed_at: datetime
    age: Age
    stale: bool = False
