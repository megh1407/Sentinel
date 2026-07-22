"""ZoneAssessmentResult — internal bundle of everything one zone's pass
through the pipeline produced.

Not part of the published output contract (`RiskDecisionPackage` is).
This exists so `SiteRiskSynthesizer` can reason across several zones'
worth of results without re-deriving them, and so the existing
single-zone `Orchestrator.handle_event()` path (already used, already
verified — see docs/RECONCILIATION_REPORT.md §5) keeps working exactly
as before: `handle_event()` now computes one of these internally and
wraps it into the existing `SystemRiskAssessment`, rather than being
rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_orchestrator_agent.domain.enums import DecisionCategory, RiskLevel
from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.models.risk_score import GlobalRiskScore, InteractionRisk, LocalRiskScore
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding


@dataclass(frozen=True, slots=True)
class ZoneAssessmentResult:
    context: RiskContext
    findings: tuple[RuleFinding, ...]
    local: LocalRiskScore
    interaction: InteractionRisk
    global_score: GlobalRiskScore
    severity: RiskLevel
    decision_category: DecisionCategory
    escalation_required: bool
    manual_review_required: bool
