"""MaintenanceContext value object (Phase 2.2 §4.1, §4.2).

Distinct from `EquipmentContext.health_index`/`overdue_tasks` — this
object realizes Maintenance Intelligence's dedicated analysis payload
(Phase 1 §4.4), which ContextBuilder's maintenance-enrichment step
(Phase 2.2 §7) cross-references against `ZoneContext.equipment_ids`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class MaintenanceContext:
    equipment_id: str
    health_index: float | None
    overdue_tasks: tuple[str, ...] = field(default_factory=tuple)
    confidence: ConfidenceScore = field(default_factory=lambda: ConfidenceScore(0.0))
    analyzed_at: datetime | None = None
    age: Age | None = None
    stale: bool = False
