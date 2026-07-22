"""application/orchestration_pipeline.py — the canonical Orchestrator.

This is the file the master prompt's §19 pipeline diagram maps onto.
It does not replace `application/scoring_pipeline.py`'s
`OperationalContextPipeline` — that class's own docstring says future
phases "extend this class in place rather than introducing a second
orchestrator," and it already correctly owns Context Building and
Correlation (steps 1-7 of §19). This file is that extension: it takes
`OperationalContextPipeline`'s output (a correlated `RiskContext`) and
completes the remaining §19 steps — RuleEngine, RiskScorer,
cross-zone/cascade analysis, DecisionEngine, ExplanationBuilder,
EventPublisher — that had no implementation anywhere in either source
snapshot (see docs/RECONCILIATION_REPORT.md §5).

    handle_event(dto)
        -> OperationalContextPipeline.handle(dto)   [existing]
             context_builder.update / snapshot
             correlation_engine.correlate_and_attach
        -> RuleEngine.evaluate                       [new]
        -> RiskScorer.score                          [new]
        -> CrossZoneRiskAnalyzer.analyze              [new]
        -> DecisionEngine.synthesize / classify        [new]
        -> ExplanationBuilder.build                    [new]
        -> EventPublisher.publish                      [new]
        -> SystemRiskAssessment                        [new, returned]

Failure handling (master prompt §14): a `ContextValidationError` raised
by the context stage propagates unchanged — this file adds no new
try/except around it, so the existing DLQ-routing contract in
`handlers/consumers.py` keeps working exactly as before. Every stage
this file adds is a pure, exception-light domain computation (no I/O
until `EventPublisher.publish`), so there is deliberately little new
failure surface here to handle.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from risk_orchestrator_agent.application.scoring_pipeline import OperationalContextPipeline
from risk_orchestrator_agent.domain.decision.decision_engine import DecisionEngine
from risk_orchestrator_agent.domain.explanation.explanation_builder import ExplanationBuilder
from risk_orchestrator_agent.domain.models.system_risk_assessment import SystemRiskAssessment
from risk_orchestrator_agent.domain.models.zone_assessment_result import ZoneAssessmentResult
from risk_orchestrator_agent.domain.ports.history_repository_port import HistoryRepositoryPort
from risk_orchestrator_agent.domain.rules.rule_engine import RuleEngine
from risk_orchestrator_agent.domain.scoring.cross_zone import CrossZoneRiskAnalyzer
from risk_orchestrator_agent.domain.scoring.risk_scorer import RiskScorer
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.handlers.publishers import EventPublisher

logger = logging.getLogger(__name__)


class OrchestrationMetrics:
    """Extends `ContextPipelineMetrics` (already tracked inside
    `OperationalContextPipeline.metrics`) with the stages this file
    owns, so `orchestration_started` ... `orchestration_completed`
    (master prompt §16) are all observable from one place."""

    def __init__(self) -> None:
        self.rule_evaluation_time_ms_last: float = 0.0
        self.scoring_time_ms_last: float = 0.0
        self.decision_time_ms_last: float = 0.0
        self.publish_time_ms_last: float = 0.0
        self.assessments_total: int = 0
        self.escalations_total: int = 0
        self.partial_assessments_total: int = 0


class Orchestrator:
    """The canonical Orchestrator (master prompt §1, §19). One instance
    per running agent process; constructed once in `main.py` with every
    dependency already resolved."""

    def __init__(
        self,
        context_pipeline: OperationalContextPipeline,
        rule_engine: RuleEngine,
        risk_scorer: RiskScorer,
        cross_zone_analyzer: CrossZoneRiskAnalyzer,
        decision_engine: DecisionEngine,
        explanation_builder: ExplanationBuilder,
        publisher: EventPublisher,
        history_port: HistoryRepositoryPort | None = None,
    ) -> None:
        self._context_pipeline = context_pipeline
        self._rule_engine = rule_engine
        self._risk_scorer = risk_scorer
        self._cross_zone_analyzer = cross_zone_analyzer
        self._decision_engine = decision_engine
        self._explanation_builder = explanation_builder
        self._publisher = publisher
        self._history_port = history_port
        self.metrics = OrchestrationMetrics()

    async def assess_zone(self, dto: AgentResultDTO) -> ZoneAssessmentResult:
        """Steps 1-13 of master prompt §19 for a single zone: context
        through decision classification, with no publication side
        effect. Extracted so `SiteOrchestrator` (application/
        site_orchestration.py) can run this per zone and then reason
        across several zones at once, without duplicating this logic or
        publishing a per-zone assessment that a site-level decision is
        about to supersede.
        """
        logger.info(
            "orchestration_started",
            extra={"event_id": dto.event_id, "zone_id": dto.zone_id, "correlation_id": dto.correlation_id},
        )

        # Steps 1-7 of master prompt §19: validate/build context/correlate.
        # Raises ContextValidationError unchanged on hard failure — see
        # module docstring on why this file adds no new handling here.
        context = await self._context_pipeline.handle(dto)
        logger.info("context_built", extra={"zone_id": dto.zone_id, "correlation_id": dto.correlation_id})

        t0 = time.perf_counter()
        findings = self._rule_engine.evaluate(context)
        self.metrics.rule_evaluation_time_ms_last = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        local_score = self._risk_scorer.score(context, findings)
        interaction_risk = self._cross_zone_analyzer.analyze(context, findings)
        self.metrics.scoring_time_ms_last = (time.perf_counter() - t1) * 1000
        logger.info(
            "risk_synthesis_completed",
            extra={
                "zone_id": dto.zone_id,
                "local_score": local_score.score,
                "interaction_score": interaction_risk.score,
            },
        )

        t2 = time.perf_counter()
        previous_severity = context.historical.previous_severity if context.historical else None
        global_score = self._decision_engine.synthesize(context, local_score, interaction_risk)
        severity, category, escalation_required, manual_review_required = self._decision_engine.classify(
            global_score, findings=findings, previous_severity=previous_severity
        )
        self.metrics.decision_time_ms_last = (time.perf_counter() - t2) * 1000
        logger.info(
            "decision_created",
            extra={"zone_id": dto.zone_id, "severity": severity.value, "decision_category": category.value},
        )

        return ZoneAssessmentResult(
            context=context,
            findings=findings,
            local=local_score,
            interaction=interaction_risk,
            global_score=global_score,
            severity=severity,
            decision_category=category,
            escalation_required=escalation_required,
            manual_review_required=manual_review_required,
        )

    async def handle_event(self, dto: AgentResultDTO) -> SystemRiskAssessment:
        zone_result = await self.assess_zone(dto)
        context = zone_result.context
        findings = zone_result.findings
        global_score = zone_result.global_score
        severity = zone_result.severity
        category = zone_result.decision_category
        escalation_required = zone_result.escalation_required
        manual_review_required = zone_result.manual_review_required
        interaction_risk = zone_result.interaction
        previous_severity = context.historical.previous_severity if context.historical else None

        contributing_factors = self._explanation_builder.contributing_factors(global_score, findings)
        explanation_text = self._explanation_builder.build(global_score, findings, severity=severity.value)

        assessment = SystemRiskAssessment(
            assessment_id=str(uuid.uuid4()),
            zone_id=dto.zone_id,
            site_id=dto.site_id,
            event_id=dto.event_id,
            correlation_id=dto.correlation_id,
            computed_at=datetime.now(timezone.utc),
            global_score=global_score,
            severity=severity,
            decision_category=category,
            confidence=context.confidence_model.aggregate_confidence,
            contributing_factors=contributing_factors,
            propagation_paths=interaction_risk.propagation_paths,
            explanation=explanation_text,
            escalation_required=escalation_required,
            manual_review_required=manual_review_required,
            analysis_completeness=global_score.analysis_completeness,
            missing_domains=global_score.missing_domains,
            risk_level_changed=(previous_severity is not None and previous_severity != severity.value),
            previous_severity=previous_severity,
        )

        t3 = time.perf_counter()
        await self._publisher.publish(assessment)
        self.metrics.publish_time_ms_last = (time.perf_counter() - t3) * 1000

        self.metrics.assessments_total += 1
        if assessment.escalation_required:
            self.metrics.escalations_total += 1
        if assessment.analysis_completeness == "partial":
            self.metrics.partial_assessments_total += 1

        logger.info(
            "orchestration_completed",
            extra={
                "event_id": dto.event_id,
                "zone_id": dto.zone_id,
                "assessment_id": assessment.assessment_id,
                "severity": severity.value,
                "escalation_required": escalation_required,
            },
        )
        return assessment
