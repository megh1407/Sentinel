"""Numeric measurement value objects.

Every class below validates itself at construction time (never after) so
an invalid value can never exist as a live object anywhere in this
codebase — consistent with the implementation brief's "invalid values
must fail immediately" requirement and CSEGS §1.1's Fail Fast principle.
"""

from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.domain.enums.event_types import ConfidenceDerivationMethod
from risk_orchestrator_agent.domain.validators.value_validators import (
    validate_coordinate,
    validate_probability,
    validate_risk_score,
)
from risk_orchestrator_agent.shared.serialization.serializer import Serializable


@dataclasses.dataclass(frozen=True, slots=True)
class RiskScore(Serializable):
    """The 0-100 numeric outcome of one scoring cycle (Phase 2.5 §5).

    Realizes `RiskScore` as a Value Object: two `RiskScore(79)` instances
    are equal and interchangeable — no identity of their own.
    """

    value: int

    def __post_init__(self) -> None:
        validate_risk_score(self.value)

    def __int__(self) -> int:  # pragma: no cover - trivial
        return self.value


@dataclasses.dataclass(frozen=True, slots=True)
class ConfidenceScore(Serializable):
    """A [0,1] certainty measure attached to any claim (Phase 2.5 §5)."""

    value: float
    derivation_method: ConfidenceDerivationMethod = ConfidenceDerivationMethod.MODEL_BASED

    def __post_init__(self) -> None:
        validate_probability(self.value, field_name="confidence")

    def __float__(self) -> float:  # pragma: no cover - trivial
        return self.value

    def is_below(self, threshold: float) -> bool:
        """Convenience predicate — never used to *suppress* a finding
        (Phase 2.3 §10.5), only to decide auxiliary behavior such as
        flagging `Manual Review Required` (Phase 2.4 §4.1).
        """
        return self.value < threshold


@dataclasses.dataclass(frozen=True, slots=True)
class Probability(Serializable):
    """A likelihood estimate for a forward-looking claim (Phase 2.5 §5),
    e.g., `EquipmentContext.failure_prediction.probability`.
    """

    value: float

    def __post_init__(self) -> None:
        validate_probability(self.value, field_name="probability")


@dataclasses.dataclass(frozen=True, slots=True)
class CorrelationStrength(Serializable):
    """`CorrelationFinding.strength` — how confidently two facts are the
    same real-world situation (Phase 2.3 §4.3). A structural measure,
    never a risk judgment.
    """

    value: float

    def __post_init__(self) -> None:
        validate_probability(self.value, field_name="strength")


@dataclasses.dataclass(frozen=True, slots=True)
class Coordinate(Serializable):
    """A physical (latitude, longitude) coordinate pair."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        validate_coordinate(self.latitude, self.longitude)


@dataclasses.dataclass(frozen=True, slots=True)
class GeoLocation(Serializable):
    """A named physical location, optionally with a coordinate and a
    hazard/effect radius (Phase 2.2 §10.3).
    """

    zone_id: str
    coordinate: Coordinate | None = None
    radius_m: float | None = None

    def __post_init__(self) -> None:
        if self.radius_m is not None and self.radius_m < 0:
            from risk_orchestrator_agent.domain.exceptions.base import ValidationException

            raise ValidationException(f"radius_m must be >= 0, got {self.radius_m}")
