"""Strongly typed identifier value objects.

Wrapping raw ID strings in dedicated types prevents the classic "swapped
two string arguments of the same shape" bug class, and gives every
identifier a single place to validate its format. All identifiers here
are immutable, structurally-equal Value Objects (Phase 2.5 §1.4) — two
instances with the same `value` are interchangeable.
"""

from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.domain.validators.base import validate_non_empty_string, validate_uuid
from risk_orchestrator_agent.shared.serialization.serializer import Serializable


@dataclasses.dataclass(frozen=True, slots=True)
class _StringId(Serializable):
    """Private base for every simple string-backed identifier below."""

    value: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.value, field_name=type(self).__name__)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclasses.dataclass(frozen=True, slots=True)
class _UuidId(Serializable):
    """Private base for every UUID-backed identifier below."""

    value: str

    def __post_init__(self) -> None:
        validate_uuid(self.value, field_name=type(self).__name__)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclasses.dataclass(frozen=True, slots=True)
class WorkerId(_StringId):
    """Canonical identifier for a Worker reference entity (Phase 2.5 §4.1)."""


@dataclasses.dataclass(frozen=True, slots=True)
class ZoneId(_StringId):
    """Canonical identifier for a Zone reference entity (Phase 2.5 §4.1)."""


@dataclasses.dataclass(frozen=True, slots=True)
class SiteId(_StringId):
    """Canonical identifier for a Site."""


@dataclasses.dataclass(frozen=True, slots=True)
class EquipmentId(_StringId):
    """Canonical identifier for an Equipment reference entity."""


@dataclasses.dataclass(frozen=True, slots=True)
class PermitId(_UuidId):
    """Canonical identifier for a Permit reference entity (UUID per Phase 1 §4.3)."""


@dataclasses.dataclass(frozen=True, slots=True)
class IncidentId(_StringId):
    """Canonical identifier for an Incident reference entity (Phase 1 §4.6)."""


@dataclasses.dataclass(frozen=True, slots=True)
class EventId(_UuidId):
    """Canonical identifier for a raw upstream event (Phase 1 `BaseEvent.event_id`)."""


@dataclasses.dataclass(frozen=True, slots=True)
class CorrelationId(_UuidId):
    """Canonical `correlation_id` threading one causal chain together."""


@dataclasses.dataclass(frozen=True, slots=True)
class TraceId(_StringId):
    """OpenTelemetry trace identifier (not necessarily UUID-shaped)."""


@dataclasses.dataclass(frozen=True, slots=True)
class AssessmentId(_UuidId):
    """Canonical identifier for a `RiskAssessment` aggregate (Phase 2.5 §3.2)."""


@dataclasses.dataclass(frozen=True, slots=True)
class DecisionId(_UuidId):
    """Canonical identifier for a `Decision` aggregate (Phase 2.5 §3.3)."""


@dataclasses.dataclass(frozen=True, slots=True)
class FindingId(_UuidId):
    """Canonical identifier for a `RuleFinding`/`CorrelationFinding` (Phase 2.3 §4.4)."""


@dataclasses.dataclass(frozen=True, slots=True)
class EvidenceId(_UuidId):
    """Canonical identifier for an `EvidenceItem` (Phase 2.2 §11.1)."""
