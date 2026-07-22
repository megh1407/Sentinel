"""Evidence, hazard, and other misc immutable value objects."""

from __future__ import annotations

import dataclasses
from datetime import datetime

from risk_orchestrator_agent.domain.enums.event_types import EvidenceType
from risk_orchestrator_agent.domain.enums.risk import HazardCategory
from risk_orchestrator_agent.domain.validators.base import (
    validate_non_empty_string,
    validate_timestamp,
)
from risk_orchestrator_agent.domain.validators.value_validators import validate_probability
from risk_orchestrator_agent.shared.serialization.serializer import Serializable


@dataclasses.dataclass(frozen=True, slots=True)
class EvidenceItem(Serializable):
    """A single traceable pointer from a claim to a real upstream event
    (Phase 2.2 §11.1). Immutable — evidence is never edited after capture.
    """

    evidence_id: str
    evidence_source: str
    evidence_type: EvidenceType
    confidence: float
    timestamp: datetime
    origin_agent: str
    supporting_event_ids: tuple[str, ...] = ()
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_non_empty_string(self.evidence_id, field_name="evidence_id")
        validate_non_empty_string(self.evidence_source, field_name="evidence_source")
        validate_non_empty_string(self.origin_agent, field_name="origin_agent")
        validate_probability(self.confidence, field_name="confidence")
        validate_timestamp(self.timestamp, field_name="timestamp")


@dataclasses.dataclass(frozen=True, slots=True)
class EvidenceReference(Serializable):
    """A pointer from any claim to its supporting `EvidenceItem`
    (Phase 2.5 §5) — lighter-weight than `EvidenceItem` itself, used when
    only the linkage (not the full evidence record) needs to travel.
    """

    evidence_id: str
    source_event_id: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.evidence_id, field_name="evidence_id")
        validate_non_empty_string(self.source_event_id, field_name="source_event_id")


@dataclasses.dataclass(frozen=True, slots=True)
class Hazard(Serializable):
    """A specific, named physical condition capable of causing harm
    (Phase 2.5 §2) — the raw phenomenon a risk is assessed *about*.
    """

    hazard_type: HazardCategory
    measured_value: float
    unit: str
    threshold_breach: bool = False
    trend: str = "stable"  # "rising" | "falling" | "stable"
    sensor_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_non_empty_string(self.unit, field_name="unit")
        if self.trend not in ("rising", "falling", "stable"):
            from risk_orchestrator_agent.domain.exceptions.base import ValidationException

            raise ValidationException(f"trend must be rising/falling/stable, got {self.trend!r}")


@dataclasses.dataclass(frozen=True, slots=True)
class RiskReason(Serializable):
    """A single, human-readable named reason contributing to a risk
    finding — the atomic unit `reasoning_steps` (Phase 2.1 §3.8) is built
    from.
    """

    factor_name: str
    description: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.factor_name, field_name="factor_name")
        validate_non_empty_string(self.description, field_name="description")


@dataclasses.dataclass(frozen=True, slots=True)
class TimeWindow(Serializable):
    """A bounded time span (Phase 2.2 §9's temporal windows)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        validate_timestamp(self.start, field_name="start")
        validate_timestamp(self.end, field_name="end")
        if self.end < self.start:
            from risk_orchestrator_agent.domain.exceptions.base import ValidationException

            raise ValidationException("TimeWindow.end must not precede TimeWindow.start")

    def contains(self, instant: datetime) -> bool:
        return self.start <= instant <= self.end


@dataclasses.dataclass(frozen=True, slots=True)
class Threshold(Serializable):
    """A configured boundary value a reading is compared against
    (Phase 2.5 §5)."""

    metric_name: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.metric_name, field_name="metric_name")
        validate_non_empty_string(self.unit, field_name="unit")
