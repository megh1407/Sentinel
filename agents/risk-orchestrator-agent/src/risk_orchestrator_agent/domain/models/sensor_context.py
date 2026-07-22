"""SensorContext value object (Phase 2.2 §4.1, §4.2).

Realizes the Environment Intelligence domain — named `SensorContext`,
matching the class name already established in Phase 2.2's object tree
and FRS §4.1/§4.2, not the source brief's "EnvironmentContext" (Section
6.1 naming-consistency rule of Phase 3.1: class names match the
component name already established in prior documents exactly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class Hazard:
    hazard_type: str
    measured_value: float
    unit: str
    threshold_ppm: float | None
    threshold_breach: bool
    trend: str  # rising | falling | stable
    sensor_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SensorContext:
    hazards: tuple[Hazard, ...]
    evacuation_required: bool
    affected_zones: tuple[str, ...]
    confidence: ConfidenceScore
    analyzed_at: datetime
    age: Age
    stale: bool = False
