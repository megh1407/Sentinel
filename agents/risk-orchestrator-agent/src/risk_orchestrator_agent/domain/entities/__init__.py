"""Domain entities (Phase 2.5 §3, §4). Entities carry only state — no
business logic beyond invariant enforcement and simple, mechanical
lifecycle helpers (`touch`, `transition_to`, `snapshot`)."""

from risk_orchestrator_agent.domain.entities.assessment_entities import (
    CompoundRisk,
    DecisionExplanation,
    EmergencyAssessment,
    HistoricalRisk,
    LiveRiskSnapshot,
    Recommendation,
    RecommendationSet,
    RiskAssessment,
    RiskContributor,
)
from risk_orchestrator_agent.domain.entities.base import Entity
from risk_orchestrator_agent.domain.entities.context_entities import (
    CorrelationContext,
    EnvironmentContext,
    EquipmentContext,
    HistoricalContext,
    IncidentContext,
    MaintenanceContext,
    NeighborZoneContext,
    PermitContext,
    RiskContext,
    WorkerContext,
    ZoneContext,
)
from risk_orchestrator_agent.domain.entities.decision_entities import (
    Decision,
    DecisionRecord,
    EventEnvelope,
)

__all__ = [
    "CompoundRisk",
    "CorrelationContext",
    "Decision",
    "DecisionExplanation",
    "DecisionRecord",
    "EmergencyAssessment",
    "Entity",
    "EnvironmentContext",
    "EquipmentContext",
    "EventEnvelope",
    "HistoricalContext",
    "HistoricalRisk",
    "IncidentContext",
    "LiveRiskSnapshot",
    "MaintenanceContext",
    "NeighborZoneContext",
    "PermitContext",
    "Recommendation",
    "RecommendationSet",
    "RiskAssessment",
    "RiskContext",
    "RiskContributor",
    "WorkerContext",
    "ZoneContext",
]
