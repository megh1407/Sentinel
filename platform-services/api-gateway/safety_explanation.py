"""safety_explanation.py -- deterministic Safety Explanation Builder.

Converts a verified SystemRiskAssessment (the same dict shape produced by
main.py's _serialize_assessment, already proven real against live Kafka +
Neo4j + Postgres data) into a structured, human-readable explanation.

This module owns NOTHING about risk calculation. It reads verified fields
only -- it never recomputes score, severity, or decision. That authority
stays entirely with the Risk Orchestrator, per the master prompt's
non-negotiable architecture rule.

Works with zero external dependencies, so it is always available even if
the LLM Safety Copilot (safety_copilot.py) is unreachable, rate-limited,
or has no API key configured yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Keyword -> (agent display name, impact label) used to attribute each
# contributing_factor string to the agent that actually produced it.
# These keywords come directly from the real factor text the agents emit
# (see environmental_intelligence_agent.py, worker_safety_agent, etc.) --
# not invented, just pattern-matched against known real output.
_AGENT_PATTERNS: list[tuple[str, str, str]] = [
    ("ppe violation", "Worker Safety Agent", "HIGH"),
    ("worker", "Worker Safety Agent", "HIGH"),
    ("toxic_gas", "Environmental Intelligence Agent", "CRITICAL"),
    ("flammable_gas", "Environmental Intelligence Agent", "CRITICAL"),
    ("high_temperature", "Environmental Intelligence Agent", "CRITICAL"),
    ("methane", "Environmental Intelligence Agent", "CRITICAL"),
    ("evacuation is required", "Environmental Intelligence Agent", "CRITICAL"),
    ("permit", "Permit Intelligence Agent", "HIGH"),
    ("shares_ventilation", "Zone Intelligence Agent (topology)", "MODERATE"),
    ("adjacent", "Zone Intelligence Agent (topology)", "MODERATE"),
    ("evacuation_route", "Zone Intelligence Agent (topology)", "MODERATE"),
]

_SEVERITY_LABELS = {
    "negligible": "no meaningful risk",
    "low": "low risk",
    "moderate": "moderate risk",
    "high": "elevated risk",
    "critical": "critical risk",
    "catastrophic": "a catastrophic, emergency-level risk",
}


@dataclass
class AgentContribution:
    agent: str
    impact: str
    findings: list[str] = field(default_factory=list)


@dataclass
class SafetyExplanation:
    """Structured explanation for one SystemRiskAssessment. Every field
    here is derived from verified assessment data -- nothing is invented."""

    assessment_id: str
    zone_id: str
    severity: str
    decision_category: str
    global_score: float

    summary: str
    situation: str
    why_this_matters: str
    primary_hazard: str | None

    top_risk_factors: list[str]
    agent_contributions: list[AgentContribution]

    is_compound_risk: bool
    compound_risk_explanation: str | None

    affected_zones: list[str]
    propagation_impact: list[str]

    immediate_action: str | None
    confidence: float
    analysis_completeness: str
    missing_domains: list[str]
    analysis_limitations: str | None

    def to_dict(self) -> dict:
        return {
            "assessment_id": self.assessment_id,
            "zone_id": self.zone_id,
            "severity": self.severity,
            "decision_category": self.decision_category,
            "global_score": self.global_score,
            "summary": self.summary,
            "situation": self.situation,
            "why_this_matters": self.why_this_matters,
            "primary_hazard": self.primary_hazard,
            "top_risk_factors": self.top_risk_factors,
            "agent_contributions": [
                {"agent": c.agent, "impact": c.impact, "findings": c.findings}
                for c in self.agent_contributions
            ],
            "is_compound_risk": self.is_compound_risk,
            "compound_risk_explanation": self.compound_risk_explanation,
            "affected_zones": self.affected_zones,
            "propagation_impact": self.propagation_impact,
            "immediate_action": self.immediate_action,
            "confidence": self.confidence,
            "analysis_completeness": self.analysis_completeness,
            "missing_domains": self.missing_domains,
            "analysis_limitations": self.analysis_limitations,
        }


def _attribute_factor(factor: str) -> tuple[str, str]:
    """Best-effort mapping of a real contributing_factors string to the
    agent that most likely produced it, via keyword match against known
    real output patterns. Falls back to 'Risk Orchestrator' (still true --
    the Orchestrator did produce the string) rather than inventing a
    specific agent it can't actually attribute."""
    lowered = factor.lower()
    for keyword, agent, impact in _AGENT_PATTERNS:
        if keyword in lowered:
            return agent, impact
    return "Risk Orchestrator", "MODERATE"


def build_explanation(assessment: dict, action: dict | None = None) -> SafetyExplanation:
    """Pure function: verified assessment dict (+ optional action dict from
    /api/action-requests) in, structured explanation out. No I/O, no LLM,
    no recalculation of anything the Risk Orchestrator already decided."""

    zone_id = assessment["zone_id"]
    severity = assessment["severity"]
    decision = assessment["decision_category"]
    score = assessment["global_score"]
    factors: list[str] = list(assessment.get("contributing_factors", []))
    propagation_paths = assessment.get("propagation_paths", [])
    affected_zones = sorted({zone_id, *[p["to_zone"] for p in propagation_paths]})

    # Agent contributions: group real factors by the agent that produced them.
    by_agent: dict[str, AgentContribution] = {}
    for f in factors:
        agent, impact = _attribute_factor(f)
        if agent not in by_agent:
            by_agent[agent] = AgentContribution(agent=agent, impact=impact, findings=[])
        by_agent[agent].findings.append(f)
    agent_contributions = list(by_agent.values())

    # Compound risk: real, not assumed -- only true if 2+ *distinct* agents
    # (excluding topology) contributed a factor to this specific assessment.
    contributing_agents = {c.agent for c in agent_contributions if "topology" not in c.agent}
    is_compound = len(contributing_agents) >= 2

    primary_hazard = factors[0] if factors else None

    severity_label = _SEVERITY_LABELS.get(severity, severity)
    summary = (
        f"{'Emergency' if decision == 'emergency' else severity.capitalize()} in {zone_id}: "
        f"{primary_hazard.rstrip('.') if primary_hazard else 'no active hazard'}."
    )
    if len(affected_zones) > 1:
        summary += f" May affect {', '.join(z for z in affected_zones if z != zone_id)}."

    situation = (
        f"{zone_id} is currently assessed at {severity_label} "
        f"(global risk score {score:.1f}/100)."
    )

    if is_compound:
        agent_list = ", ".join(sorted(contributing_agents))
        why_this_matters = (
            f"This risk is elevated because multiple independent safety domains "
            f"({agent_list}) detected conditions at the same time. The Risk "
            f"Orchestrator correlated these findings rather than treating them as "
            f"isolated alerts, which is why the combined risk is higher than any "
            f"single factor alone would produce."
        )
        compound_risk_explanation = (
            "COMPOUND RISK DETECTED: " +
            " + ".join(f"{c.agent} \u2192 {c.findings[0]}" for c in agent_contributions if "topology" not in c.agent) +
            ". The Risk Orchestrator correlated these findings and increased the system risk accordingly."
        )
    else:
        why_this_matters = (
            f"This assessment is driven by a single domain finding. "
            f"{primary_hazard if primary_hazard else 'No specific hazard was recorded.'}"
        )
        compound_risk_explanation = None

    propagation_impact = []
    for p in propagation_paths:
        rel = p["relationship_type"].replace("_", " ")
        propagation_impact.append(
            f"The hazard in {p['from_zone']} may extend to {p['to_zone']} because the two zones "
            f"are connected by {rel}."
        )

    immediate_action = None
    if action:
        immediate_action = action.get("explanation") or (
            f"{action.get('action_type', 'RESPOND').replace('_', ' ')} "
            f"(urgency {action.get('urgency', 'UNKNOWN')})"
        )

    analysis_limitations = None
    missing = assessment.get("missing_domains", [])
    if missing:
        analysis_limitations = (
            f"This assessment is {assessment.get('analysis_completeness', 'partial')}: "
            f"the following domains have not yet reported for this zone and are not "
            f"reflected in the score -- {', '.join(missing)}."
        )

    top_risk_factors = factors[:5]

    return SafetyExplanation(
        assessment_id=assessment["assessment_id"],
        zone_id=zone_id,
        severity=severity,
        decision_category=decision,
        global_score=score,
        summary=summary,
        situation=situation,
        why_this_matters=why_this_matters,
        primary_hazard=primary_hazard,
        top_risk_factors=top_risk_factors,
        agent_contributions=agent_contributions,
        is_compound_risk=is_compound,
        compound_risk_explanation=compound_risk_explanation,
        affected_zones=affected_zones,
        propagation_impact=propagation_impact,
        immediate_action=immediate_action,
        confidence=assessment.get("confidence", 0.0),
        analysis_completeness=assessment.get("analysis_completeness", "unknown"),
        missing_domains=missing,
        analysis_limitations=analysis_limitations,
    )
