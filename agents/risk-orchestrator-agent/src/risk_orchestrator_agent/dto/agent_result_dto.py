"""dto/agent_result_dto.py (FRS §6).

Maps the wire-format `AgentResult` envelope (Phase 1 §4) — common to all
six inbound `*.analysis.v1` topics — into a typed, validated DTO. Domain
payload parsing into the six sub-context Value Objects (Phase 2.2 §4) is
also performed here, since that mapping is itself wire-format ↔ domain
translation (FRS §6's "DTOs translate wire format ↔ domain models" rule),
never business logic.

Re-validates the envelope even though schema-registry validation already
happened upstream (Phase 1 §4.8): confidence in [0,1], processing_time_ms
>= 0, required fields present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

DOMAIN_BY_RESULT_TYPE: dict[str, str] = {
    "worker_analysis": "worker",
    "zone_analysis": "zone",
    "permit_analysis": "permit",
    "maintenance_analysis": "maintenance",
    "environment_analysis": "sensor",
    "incident_analysis": "incident",
}


class AgentResultValidationError(ValueError):
    """Raised when an inbound envelope fails re-validation (Phase 1 §4.8).
    Caught by handlers/consumers.py and routed to DLQ — never propagated
    into domain logic."""


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    raise AgentResultValidationError(f"Unparseable timestamp: {value!r}")


@dataclass(frozen=True, slots=True)
class AgentResultDTO:
    """The universal `AgentResult` envelope (Phase 1 §4), plus its
    domain-specific `payload` retained as a raw mapping — parsed into a
    typed sub-context by `domain/context/context_builder.py`'s merge
    logic, keyed off `domain_name` below."""

    event_id: str
    event_type: str
    event_version: int
    timestamp: datetime
    source: str
    site_id: str
    zone_id: str
    correlation_id: str
    causation_id: str | None
    schema_version: str

    agent_id: str
    agent_version: str
    input_events: tuple[str, ...]
    result_type: str
    confidence: float
    processing_time_ms: int
    error: dict[str, Any] | None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def domain_name(self) -> str:
        """Maps `result_type` to this codebase's internal domain key
        (Phase 2.2 §4.2 naming: environment -> `sensor`)."""
        try:
            return DOMAIN_BY_RESULT_TYPE[self.result_type]
        except KeyError as exc:
            raise AgentResultValidationError(
                f"Unknown result_type: {self.result_type!r}"
            ) from exc

    @property
    def analyzed_at(self) -> datetime:
        raw = self.payload.get("analyzed_at")
        return _parse_timestamp(raw) if raw is not None else self.timestamp

    @property
    def has_error(self) -> bool:
        """A populated `error` object is a confidence-reducing signal
        (Phase 1 §4.8), never discarded — treated as `absent`, per
        Phase 2.2 §8.4's decision matrix, not as a competing "no risk"
        claim."""
        return self.error is not None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "AgentResultDTO":
        """Deserializes and re-validates a raw envelope dict (already
        deserialized from Kafka bytes by `sentinel_eventbus`, per
        FRS §6). Raises `AgentResultValidationError` on any violation —
        never raises a bare `KeyError`/`TypeError` across this boundary.
        """
        try:
            required = (
                "event_id",
                "event_type",
                "event_version",
                "timestamp",
                "source",
                "site_id",
                "zone_id",
                "correlation_id",
                "schema_version",
                "agent_id",
                "agent_version",
                "result_type",
                "confidence",
                "processing_time_ms",
            )
            missing = [f for f in required if f not in raw]
            if missing:
                raise AgentResultValidationError(f"Missing required fields: {missing}")

            confidence = float(raw["confidence"])
            if not (0.0 <= confidence <= 1.0):
                raise AgentResultValidationError(
                    f"confidence out of range [0,1]: {confidence}"
                )

            processing_time_ms = int(raw["processing_time_ms"])
            if processing_time_ms < 0:
                raise AgentResultValidationError(
                    f"processing_time_ms must be >= 0: {processing_time_ms}"
                )

            return cls(
                event_id=str(raw["event_id"]),
                event_type=str(raw["event_type"]),
                event_version=int(raw["event_version"]),
                timestamp=_parse_timestamp(raw["timestamp"]),
                source=str(raw["source"]),
                site_id=str(raw["site_id"]),
                zone_id=str(raw["zone_id"]),
                correlation_id=str(raw["correlation_id"]),
                causation_id=(str(raw["causation_id"]) if raw.get("causation_id") else None),
                schema_version=str(raw["schema_version"]),
                agent_id=str(raw["agent_id"]),
                agent_version=str(raw["agent_version"]),
                input_events=tuple(raw.get("input_events", ()) or ()),
                result_type=str(raw["result_type"]),
                confidence=confidence,
                processing_time_ms=processing_time_ms,
                error=raw.get("error"),
                payload=dict(raw.get("payload", {}) or {}),
            )
        except AgentResultValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentResultValidationError(f"Malformed AgentResult envelope: {exc}") from exc
