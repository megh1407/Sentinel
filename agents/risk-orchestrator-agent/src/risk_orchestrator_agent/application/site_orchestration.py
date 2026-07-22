"""application/site_orchestration.py — SiteOrchestrator.

The multi-zone counterpart to `Orchestrator` (orchestration_pipeline.py).
Runs the existing, verified per-zone pipeline (`Orchestrator.assess_zone`)
once per zone in a decision cycle, then hands every zone's result to
`SiteRiskSynthesizer` and `ResponseRecommendationEngine` to build one
`RiskDecisionPackage` — the output contract specified directly by the
user, matching their `decision_id` / `risk_assessment` / `zone_risks` /
`interaction_risks` / `permit_risks` / `incident_context` /
`risk_breakdown` / `risk_reasoning` / `emergency_decision` /
`recommended_response` / `response_actions` / `provenance` shape.

Caller decides which zones belong to one cycle (e.g., a zone that just
raised an event plus its known neighbors) — this class does not discover
that grouping itself; see docs/RECONCILIATION_REPORT.md §6 gap #1 on why
a fully autonomous, continuously-maintained site-wide grouping needs a
`SiteState` aggregate that doesn't exist yet.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from risk_orchestrator_agent.application.orchestration_pipeline import Orchestrator
from risk_orchestrator_agent.domain.decision.response_recommender import ResponseRecommendationEngine
from risk_orchestrator_agent.domain.decision.site_synthesizer import SiteRiskSynthesizer
from risk_orchestrator_agent.domain.models.risk_decision_package import RiskDecisionPackage
from risk_orchestrator_agent.domain.models.zone_assessment_result import ZoneAssessmentResult
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.handlers.publishers import EventPublisher

logger = logging.getLogger(__name__)


def _decision_id() -> str:
    now = datetime.now(timezone.utc)
    return f"RISK-{now.year}-{uuid.uuid4().hex[:6].upper()}"


class SiteOrchestrator:
    def __init__(
        self,
        orchestrator: Orchestrator,
        site_synthesizer: SiteRiskSynthesizer,
        response_recommender: ResponseRecommendationEngine,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._site_synthesizer = site_synthesizer
        self._response_recommender = response_recommender
        self._publisher = publisher

    async def handle_site_cycle(self, dtos: list[AgentResultDTO]) -> RiskDecisionPackage:
        if not dtos:
            raise ValueError("handle_site_cycle() requires at least one zone's AgentResultDTO")

        results: list[ZoneAssessmentResult] = []
        for dto in dtos:
            result = await self._orchestrator.assess_zone(dto)
            results.append(result)

        (
            risk_assessment,
            zone_risks,
            interaction_risks,
            permit_risks,
            incident_context,
            risk_breakdown,
            risk_reasoning,
            emergency_decision,
            provenance,
        ) = self._site_synthesizer.synthesize(results)

        recommended_response = self._response_recommender.recommend(
            results,
            is_emergency=emergency_decision.is_emergency,
            overall_level=risk_assessment.overall_risk_level.lower(),
        )

        package = RiskDecisionPackage(
            decision_id=_decision_id(),
            timestamp=datetime.now(timezone.utc),
            risk_assessment=risk_assessment,
            zone_risks=zone_risks,
            interaction_risks=interaction_risks,
            permit_risks=permit_risks,
            incident_context=incident_context,
            risk_breakdown=risk_breakdown,
            risk_reasoning=risk_reasoning,
            emergency_decision=emergency_decision,
            response_type=recommended_response.response_type,
            response_priority=recommended_response.priority,
            requires_human_confirmation=recommended_response.requires_human_confirmation,
            response_actions=recommended_response.actions,
            provenance=provenance,
        )

        logger.info(
            "site_decision_created",
            extra={
                "decision_id": package.decision_id,
                "overall_risk_level": risk_assessment.overall_risk_level,
                "risk_scope": risk_assessment.risk_scope,
                "is_emergency": emergency_decision.is_emergency,
            },
        )

        # NOTE: `self._publisher` (accepted for future use) is not called
        # here. `handlers/publishers.EventPublisher.publish()` is typed
        # against `SystemRiskAssessment`, not `RiskDecisionPackage` — a
        # site-level publish path needs either a second publisher method
        # or a widened protocol, not a silent type mismatch. Left for the
        # caller to publish `package.to_dict()` explicitly until that
        # protocol decision is made.

        return package
