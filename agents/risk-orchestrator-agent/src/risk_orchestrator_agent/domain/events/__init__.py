"""Domain and integration event contracts (Phase 1 §4/§5, Phase 2.5 §6)."""

from risk_orchestrator_agent.domain.events.base import DomainEvent
from risk_orchestrator_agent.domain.events.domain_events import (
    AssessmentExpired,
    CompoundRiskDetected,
    DecisionClosed,
    DecisionGenerated,
    EmergencyTriggered,
    EnvironmentUpdated,
    EquipmentRiskDetected,
    IncidentClosed,
    IncidentCreated,
    PermitUpdated,
    PredictionContributed,
    RecommendationGenerated,
    RiskAssessmentCreated,
    RiskResolved,
    SiteStateChanged,
    WorkerStatusUpdated,
    ZoneIntelligenceUpdated,
)

__all__ = [
    "AssessmentExpired",
    "CompoundRiskDetected",
    "DecisionClosed",
    "DecisionGenerated",
    "DomainEvent",
    "EmergencyTriggered",
    "EnvironmentUpdated",
    "EquipmentRiskDetected",
    "IncidentClosed",
    "IncidentCreated",
    "PermitUpdated",
    "PredictionContributed",
    "RecommendationGenerated",
    "RiskAssessmentCreated",
    "RiskResolved",
    "SiteStateChanged",
    "WorkerStatusUpdated",
    "ZoneIntelligenceUpdated",
]
