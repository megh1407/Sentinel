"""SystemRiskAssessment — the Orchestrator's final, system-level output.

Directly realizes the schema the master prompt requires in §12: never
just a number, always the traceable breakdown of why. This is what
`handlers/publishers.py`'s EventPublisher publishes downstream, and what
`ExplanationBuilder` renders into `explanation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.enums import DecisionCategory, RiskLevel
from risk_orchestrator_agent.domain.models.risk_score import GlobalRiskScore, PropagationStep


@dataclass(frozen=True, slots=True)
class SystemRiskAssessment:
    assessment_id: str
    zone_id: str
    site_id: str
    event_id: str
    correlation_id: str
    computed_at: datetime

    global_score: GlobalRiskScore
    severity: RiskLevel
    decision_category: DecisionCategory
    confidence: float

    contributing_factors: tuple[str, ...] = field(default_factory=tuple)
    propagation_paths: tuple[PropagationStep, ...] = field(default_factory=tuple)
    explanation: str = ""

    escalation_required: bool = False
    manual_review_required: bool = False

    # Master prompt §14: "3 of 5 agents completed... the Orchestrator
    # must know analysis_completeness = PARTIAL" — never presented as a
    # fully complete assessment when it isn't.
    analysis_completeness: str = "complete"  # "complete" | "partial"
    missing_domains: tuple[str, ...] = field(default_factory=tuple)

    risk_level_changed: bool = False
    previous_severity: str | None = None
