"""Abstract repository and engine interfaces (Protocols only, no
implementation) — the seam between the domain layer and every future
infrastructure/business-logic implementation phase."""

from risk_orchestrator_agent.domain.interfaces.engines import (
    ContextBuilderInterface,
    CorrelationEngineInterface,
    DecisionEngineInterface,
    EventRouterInterface,
    ExplanationBuilderInterface,
    MetricsCollectorInterface,
    PredictionEngineInterface,
    RecommendationEngineInterface,
    RiskScorerInterface,
    RuleEngineInterface,
)
from risk_orchestrator_agent.domain.interfaces.repositories import (
    ContextRepository,
    EquipmentRepository,
    HistoricalRepository,
    IncidentRepository,
    RecommendationRepository,
    RiskRepository,
    WorkerRepository,
    ZoneRepository,
)

__all__ = [
    "ContextBuilderInterface",
    "ContextRepository",
    "CorrelationEngineInterface",
    "DecisionEngineInterface",
    "EquipmentRepository",
    "EventRouterInterface",
    "ExplanationBuilderInterface",
    "HistoricalRepository",
    "IncidentRepository",
    "MetricsCollectorInterface",
    "PredictionEngineInterface",
    "RecommendationEngineInterface",
    "RecommendationRepository",
    "RiskRepository",
    "RiskScorerInterface",
    "RuleEngineInterface",
    "WorkerRepository",
    "ZoneRepository",
]
