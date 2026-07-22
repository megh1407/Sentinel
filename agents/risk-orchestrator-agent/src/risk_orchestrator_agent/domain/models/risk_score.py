"""Risk score value objects.

Models the master-prompt-mandated distinction between LOCAL risk (what
one zone's own facts justify) and SYSTEM risk (local + interaction +
cascade). Kept as three explicit, separately-populated structures rather
than one flat score so double counting is structurally hard to introduce
by accident: `GlobalRiskScore.value` is computed once, in
`domain/decision/decision_engine.py`, from these three inputs — nothing
else in the codebase is allowed to also sum them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LocalRiskScore:
    """What this zone's own RuleFindings justify, in isolation. Never
    itself the final answer — see `RiskContext.zone_id` docstring on why
    "Zone A = safe, Zone B = safe, Zone C = safe" must not collapse
    straight to "system = safe"."""

    zone_id: str
    score: float  # 0-100
    contributor_rule_ids: tuple[str, ...]
    partial_weighting: bool  # true if context.quality.completeness < 1.0


@dataclass(frozen=True, slots=True)
class PropagationStep:
    from_zone_id: str
    to_zone_id: str
    relationship_type: str  # e.g. "shares_ventilation", "evacuation_route_through", "adjacent"
    neighbor_state: str | None


@dataclass(frozen=True, slots=True)
class InteractionRisk:
    """Cross-zone amplification: risk this zone's condition creates *in
    combination with* a neighbor's state, over and above either zone's
    local score. Zero when neighbors exist but no risk-relevant
    relationship or elevated neighbor state was found — the absence of
    interaction is itself a meaningful, reportable finding (§8 of the
    master prompt: "no artificial cascade risk" when zones don't
    actually interact)."""

    score: float  # 0-100, additive contribution to global score
    propagation_paths: tuple[PropagationStep, ...] = field(default_factory=tuple)
    contributing_relationship_types: tuple[str, ...] = field(default_factory=tuple)
    explanation: tuple[str, ...] = field(default_factory=tuple)
    topology_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class GlobalRiskScore:
    """The single number DecisionEngine classifies from, plus the
    traceable breakdown of how it was reached (master prompt §12: "never
    return only risk = 0.92")."""

    zone_id: str
    value: float  # 0-100
    local: LocalRiskScore
    interaction: InteractionRisk
    analysis_completeness: str  # "complete" | "partial"
    missing_domains: tuple[str, ...] = field(default_factory=tuple)
