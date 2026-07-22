"""Abstract engine interfaces — the domain-service contracts every
implementation phase's concrete engine (`domain/context/context_builder.py`,
`domain/rules/rule_engine.py`, etc., per Phase 3.1 §2) must satisfy.

No implementation lives here; per the implementation brief, this phase
defines contracts only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from risk_orchestrator_agent.domain.entities.assessment_entities import RiskAssessment
from risk_orchestrator_agent.domain.entities.context_entities import RiskContext
from risk_orchestrator_agent.domain.entities.decision_entities import EventEnvelope
from risk_orchestrator_agent.domain.responses.responses import (
    ContextBuildResult,
    CorrelationResult,
    DecisionResult,
    ExplanationResult,
    RecommendationResult,
    RiskScoreResult,
)


@runtime_checkable
class EventRouterInterface(Protocol):
    """`EventRouter` (Phase 2.1 §3.1) — subscribe, validate, route by
    `zone_id`."""

    async def route(self, envelope: EventEnvelope) -> None: ...


@runtime_checkable
class ContextBuilderInterface(Protocol):
    """`ContextBuilder` (Phase 2.2, in full)."""

    def update(self, zone_id: str, envelope: EventEnvelope) -> None: ...
    def snapshot(self, zone_id: str) -> RiskContext: ...


@runtime_checkable
class CorrelationEngineInterface(Protocol):
    """`CorrelationEngine` (Phase 2.3 §2/§4/§6)."""

    def correlate(self, context: RiskContext) -> CorrelationResult: ...


@runtime_checkable
class RuleEngineInterface(Protocol):
    """`RuleEngine` (Phase 2.3 §3/§5/§7)."""

    def evaluate(self, correlation_result: CorrelationResult, rule_set_version: str) -> list[str]: ...


@runtime_checkable
class PredictionEngineInterface(Protocol):
    """Optional/future forward-looking prediction engine (Phase 1 §5.3,
    Phase 2.4 §17)."""

    def predict(self, context: RiskContext, *, horizon_minutes: int) -> float | None: ...


@runtime_checkable
class RiskScorerInterface(Protocol):
    """`RiskScorer` (Phase 2.1 §3.5)."""

    def score(self, finding_ids: list[str], weight_table_version: str) -> RiskScoreResult: ...


@runtime_checkable
class DecisionEngineInterface(Protocol):
    """`DecisionEngine` (Phase 2.4 §2/§3/§4)."""

    def classify(
        self, score: int, contributor_ids: list[str], previous_severity: str | None
    ) -> DecisionResult: ...


@runtime_checkable
class ExplanationBuilderInterface(Protocol):
    """`ExplanationBuilder` (Phase 2.1 §3.9)."""

    def build(self, assessment: RiskAssessment) -> ExplanationResult: ...


@runtime_checkable
class RecommendationEngineInterface(Protocol):
    """`RecommendationCoordinator` (Phase 2.1 §3.9, Phase 2.4 §7)."""

    def coordinate(self, context: RiskContext, decision_category: str) -> RecommendationResult: ...


@runtime_checkable
class MetricsCollectorInterface(Protocol):
    """`MetricsCollector` (Phase 2.1 §3.14)."""

    def increment(self, name: str, *, labels: dict[str, str] | None = None) -> None: ...
    def observe(self, name: str, value: float, *, labels: dict[str, str] | None = None) -> None: ...
