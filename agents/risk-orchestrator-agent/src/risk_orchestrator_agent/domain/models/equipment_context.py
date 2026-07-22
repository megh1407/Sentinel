"""EquipmentContext value object (Phase 2.2 §4.1, §4.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class FailurePrediction:
    probability: float
    predicted_window_h: float
    failure_mode: str


@dataclass(frozen=True, slots=True)
class EquipmentContext:
    equipment_id: str
    health_index: float | None
    failure_prediction: FailurePrediction | None
    # Deliberately additive across updates (Phase 2.2 §4.2): never
    # overwritten by a newer update that happens to omit a fault still in
    # effect, until an explicit resolution event is seen. ContextBuilder's
    # merge logic enforces this, not this value object itself.
    active_faults: tuple[str, ...]
    overdue_tasks: tuple[str, ...] = field(default_factory=tuple)
    confidence: ConfidenceScore = field(default_factory=lambda: ConfidenceScore(0.0))
    analyzed_at: datetime | None = None
    age: Age | None = None
    stale: bool = False
