"""Strongly typed enumerations for the domain layer.

Every closed vocabulary in the architecture documents is represented here
as a `str, Enum` subclass so it (a) serializes trivially to JSON via
`.value`, and (b) is usable in equality/`match` checks without an
explicit `.value` unwrap, per Coding Standards §2.3's guidance on `Enum`
usage for closed, named sets of values.
"""

from risk_orchestrator_agent.domain.enums.event_types import (
    ConfidenceDerivationMethod,
    ConfidenceLevel,
    ContextType,
    EventType,
    EvidenceType,
    PredictionSource,
    RecoveryMode,
)
from risk_orchestrator_agent.domain.enums.risk import (
    CorrelationType,
    DecisionCategory,
    HazardCategory,
    RecommendationCategory,
    RecommendationPriority,
    RiskCategory,
    RiskLevel,
    RuleCategory,
    RulePriority,
)
from risk_orchestrator_agent.domain.enums.status import (
    ContextLifecycleState,
    ContextQualityFlag,
    DecisionState,
    EquipmentStatus,
    IncidentSeverity,
    IncidentStatus,
    PermitRiskLevel,
    PermitStatus,
    RiskAssessmentStatus,
    SiteOverallState,
    WorkerSafetyStatus,
    ZoneState,
)

__all__ = [
    "ConfidenceDerivationMethod",
    "ConfidenceLevel",
    "ContextLifecycleState",
    "ContextQualityFlag",
    "ContextType",
    "CorrelationType",
    "DecisionCategory",
    "DecisionState",
    "EquipmentStatus",
    "EventType",
    "EvidenceType",
    "HazardCategory",
    "IncidentSeverity",
    "IncidentStatus",
    "PermitRiskLevel",
    "PermitStatus",
    "PredictionSource",
    "RecommendationCategory",
    "RecommendationPriority",
    "RecoveryMode",
    "RiskAssessmentStatus",
    "RiskCategory",
    "RiskLevel",
    "RuleCategory",
    "RulePriority",
    "SiteOverallState",
    "WorkerSafetyStatus",
    "ZoneState",
]
