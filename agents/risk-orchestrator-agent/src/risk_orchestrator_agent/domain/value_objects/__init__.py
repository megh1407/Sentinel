"""Immutable value objects. Every class here validates itself in
`__post_init__` and is compared/hashed structurally (Phase 2.5 §1.4)."""

from risk_orchestrator_agent.domain.value_objects.evidence import (
    EvidenceItem,
    EvidenceReference,
    Hazard,
    RiskReason,
    Threshold,
    TimeWindow,
)
from risk_orchestrator_agent.domain.value_objects.identifiers import (
    AssessmentId,
    CorrelationId,
    DecisionId,
    EquipmentId,
    EventId,
    EvidenceId,
    FindingId,
    IncidentId,
    PermitId,
    SiteId,
    TraceId,
    WorkerId,
    ZoneId,
)
from risk_orchestrator_agent.domain.value_objects.scores import (
    Coordinate,
    CorrelationStrength,
    GeoLocation,
    Probability,
    RiskScore,
)
from risk_orchestrator_agent.domain.value_objects.scores import ConfidenceScore

__all__ = [
    "AssessmentId",
    "ConfidenceScore",
    "Coordinate",
    "CorrelationId",
    "CorrelationStrength",
    "DecisionId",
    "EquipmentId",
    "EventId",
    "EvidenceId",
    "EvidenceItem",
    "EvidenceReference",
    "FindingId",
    "GeoLocation",
    "Hazard",
    "IncidentId",
    "PermitId",
    "Probability",
    "RiskReason",
    "RiskScore",
    "SiteId",
    "Threshold",
    "TimeWindow",
    "TraceId",
    "WorkerId",
    "ZoneId",
]
