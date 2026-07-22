"""domain/decision/response_recommender.py — ResponseRecommendationEngine.

Fills the "Response Directive" branch of the user-specified output
contract. Stays a *recommendation* — see the user's own architecture
diagram: the Orchestrator produces the decision, a separate Response
Agent converts it into dispatched actions. This engine's output is
exactly that handoff payload, nothing more (no actual evacuation,
permit suspension, etc. is executed by this codebase).

Rule-based and deliberately simple, mirroring `domain/rules/rule_engine.
py`'s own flat-function style: each `_recommend_*` function inspects one
category of evidence and contributes zero or more `ResponseAction`s.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.enums import DecisionCategory, RiskLevel
from risk_orchestrator_agent.domain.models.response_action import RecommendedResponse, ResponseAction
from risk_orchestrator_agent.domain.models.zone_assessment_result import ZoneAssessmentResult
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding

_EVACUATE_CATEGORIES = {DecisionCategory.EVACUATION_RECOMMENDED, DecisionCategory.EMERGENCY}
_RESTRICT_CATEGORIES = {DecisionCategory.HIGH_RISK, DecisionCategory.CRITICAL_RISK}


def _recommend_for_zone(result: ZoneAssessmentResult) -> list[ResponseAction]:
    actions: list[ResponseAction] = []
    zone_id = result.context.zone_id

    if result.decision_category in _EVACUATE_CATEGORIES:
        actions.append(
            ResponseAction(
                action="EVACUATE",
                target=zone_id,
                priority="IMMEDIATE",
                reason=f"Zone {zone_id} decision category is {result.decision_category.value}",
            )
        )
    elif result.decision_category in _RESTRICT_CATEGORIES or result.interaction.score > 0:
        actions.append(
            ResponseAction(
                action="RESTRICT_ACCESS",
                target=zone_id,
                priority="IMMEDIATE" if result.severity == RiskLevel.CRITICAL else "URGENT",
                reason=f"Zone {zone_id} is {result.decision_category.value}"
                + (" with active cross-zone interaction risk" if result.interaction.score > 0 else ""),
            )
        )

    for finding in result.findings:
        if finding.rule_id in ("permit.conflict", "permit.zone_incompatible"):
            actions.append(
                ResponseAction(
                    action="SUSPEND_PERMIT",
                    target=finding.entity_refs[0] if finding.entity_refs else "UNKNOWN_PERMIT",
                    priority="IMMEDIATE" if finding.priority.value in ("critical", "high") else "URGENT",
                    reason=finding.description,
                )
            )

    return actions


def _recommend_emergency_alert(results: list[ZoneAssessmentResult], is_emergency: bool) -> list[ResponseAction]:
    if not is_emergency:
        return []
    return [
        ResponseAction(
            action="ALERT_EMERGENCY_RESPONSE_TEAM",
            target="COMMAND_CENTER",
            priority="IMMEDIATE",
            reason="Systemic emergency conditions detected across the affected zones",
        )
    ]


class ResponseRecommendationEngine:
    """Stateless domain service."""

    def recommend(
        self,
        results: list[ZoneAssessmentResult],
        *,
        is_emergency: bool,
        overall_level: str,
    ) -> RecommendedResponse:
        actions: list[ResponseAction] = []
        for result in results:
            actions.extend(_recommend_for_zone(result))
        actions.extend(_recommend_emergency_alert(results, is_emergency))

        if is_emergency:
            response_type, priority, requires_confirmation = "EMERGENCY", "IMMEDIATE", False
        elif overall_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
            response_type, priority, requires_confirmation = "ELEVATED", "URGENT", True
        elif actions:
            response_type, priority, requires_confirmation = "ELEVATED", "STANDARD", True
        else:
            response_type, priority, requires_confirmation = "NONE", "NONE", True

        return RecommendedResponse(
            response_type=response_type,
            priority=priority,
            requires_human_confirmation=requires_confirmation,
            actions=tuple(actions),
        )
