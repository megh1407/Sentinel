"""CorrelationFinding value object (Phase 2.3 §4, §5, §11).

Correlation is evidence, not judgment (Phase 2.3 §1.4): CorrelationEngine
never decides that something is *risky* — only that two or more facts are
*related*, with what strength and what evidence. Judgment belongs to
RuleEngine, out of scope for this implementation phase.

Structural equality (Phase 2.5 §5's classification nuance, §4.4): carries
a `finding_id` for evidence-linking purposes only, remains a Value Object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11 -- StrEnum was only added in 3.11
    class StrEnum(str, Enum):
        pass


class CorrelationType(StrEnum):
    """Phase 2.3 §4.1's correlation-type catalog, realized as the subset
    this implementation phase (context assembly + relationship discovery)
    is responsible for producing."""

    WORKER_ZONE = "worker_zone"
    WORKER_EQUIPMENT = "worker_equipment"
    WORKER_PERMIT = "worker_permit"
    EQUIPMENT_SENSOR = "equipment_sensor"
    EQUIPMENT_MAINTENANCE = "equipment_maintenance"
    ZONE_NEIGHBOR_ZONE = "zone_neighbor_zone"
    PERMIT_ZONE = "permit_zone"
    PERMIT_EQUIPMENT = "permit_equipment"
    ENVIRONMENT_ZONE = "environment_zone"
    INCIDENT_WORKER = "incident_worker"
    INCIDENT_EQUIPMENT = "incident_equipment"
    INCIDENT_HISTORICAL = "incident_historical"


@dataclass(frozen=True, slots=True)
class CorrelationFinding:
    finding_id: str
    correlation_type: CorrelationType
    entity_refs: tuple[str, ...]
    strength: float
    confidence: float
    summary: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    degraded: bool = False  # e.g. topology_unavailable (Phase 2.2 §14)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strength", min(1.0, max(0.0, self.strength)))
        object.__setattr__(self, "confidence", min(1.0, max(0.0, self.confidence)))