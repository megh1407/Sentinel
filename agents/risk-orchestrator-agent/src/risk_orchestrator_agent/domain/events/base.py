"""Base class for every domain/integration event contract.

Distinguishes **domain events** (internal, business-significant
occurrences, Phase 2.5 §6.1) from **integration events** (the two-to-three
real Kafka topics, Phase 1 §5) — both are modeled as `DomainEvent`
subclasses here; which ones are actually published is a `handlers/`-layer
concern (FRS §3.9), not something this module decides.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from risk_orchestrator_agent.domain.enums.event_types import EventType
from risk_orchestrator_agent.domain.validators.base import validate_non_empty_string, validate_timestamp
from risk_orchestrator_agent.domain.validators.value_validators import validate_correlation_id
from risk_orchestrator_agent.shared.serialization.serializer import Serializable
from risk_orchestrator_agent.shared.utilities.time_utils import new_uuid, utc_now


@dataclasses.dataclass(frozen=True, slots=True)
class DomainEvent(Serializable):
    """Every event carries: `event_id`, `event_type`, `version`,
    `producer`, `timestamp`, `correlation_id`, `trace_id`, `payload`,
    `metadata` — exactly the field set the implementation brief requires.

    Frozen: an event, once constructed, is never mutated (mirrors
    `RiskAssessment`'s immutability rule, Phase 2.4 §16.1, applied to
    every event, not just the published outcome).
    """

    event_type: EventType
    payload: dict = dataclasses.field(default_factory=dict)
    event_id: str = dataclasses.field(default_factory=new_uuid)
    version: int = 1
    producer: str = "risk_orchestrator_agent"
    timestamp: datetime = dataclasses.field(default_factory=utc_now)
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    metadata: dict = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.producer, field_name="producer")
        validate_timestamp(self.timestamp, field_name="timestamp")
        if self.correlation_id is not None:
            validate_correlation_id(self.correlation_id, field_name="correlation_id")
        if self.causation_id is not None:
            validate_correlation_id(self.causation_id, field_name="causation_id")
