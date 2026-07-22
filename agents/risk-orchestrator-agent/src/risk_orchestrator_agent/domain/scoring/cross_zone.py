"""domain/scoring/cross_zone.py — CrossZoneRiskAnalyzer.

Implements master prompt §8-§11: global risk must not collapse to "max of
the local risks" (or, worse, to their sum) when zones don't actually
interact, and must exceed the max local risk when they do.

**Scope honestly stated** (see docs/RECONCILIATION_REPORT.md §6, gap #3):
this analyzer only sees what one zone's `RiskContext` carries about its
neighbors — `NeighborZoneContext.neighbor_state` (a plain state string,
e.g. "danger") and `.relationship_type` (e.g. "shares_ventilation"). It
does not have the neighbor zone's own `RuleFinding`s, hazard categories,
or a live multi-zone graph traversal — those require a site-wide state
store (`domain/site_state/`, currently an empty stub — no concrete
`SiteState` aggregate exists in this codebase yet) that would run this
analysis once per site-cycle across every zone's context at once, not
once per inbound event for one zone. What is implemented here is real,
useful, and matches the master prompt's own worked example (zone A gas
leak + zone B shared ventilation + zone C ignition source) *to the
extent* zone A's own context carries zone B and C as neighbors with a
risk-relevant relationship type and a known elevated state — which is
exactly what `NeighborZoneContext` is populated with. Detecting a
*three*-hop chain the current zone isn't itself adjacent to (A -> B -> C
where the event arrived scoped to A but C is B's neighbor, not A's)
needs that future site-wide pass; this analyzer flags that limitation
via `InteractionRisk.topology_unavailable` only when the graph query
itself failed, not when the chain is simply out of this zone's
one-hop view — a distinct, still-open gap called out in the report
rather than silently glossed over here.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.enums import RuleCategory
from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.models.risk_score import InteractionRisk, PropagationStep
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding

# Relationship types that can plausibly carry a hazard or a person into
# danger, per NeighborZoneContext's own docstring vocabulary.
_PROPAGATING_RELATIONSHIPS = {"shares_ventilation", "evacuation_route_through"}
_ELEVATED_NEIGHBOR_STATES = {"warning", "danger", "evacuate", "lockdown"}


def _this_zone_has_propagating_hazard(findings: tuple[RuleFinding, ...]) -> bool:
    return any(
        f.category in (RuleCategory.ENVIRONMENTAL, RuleCategory.ZONE) and f.weight >= 0.5
        for f in findings
    )


class CrossZoneRiskAnalyzer:
    """Stateless domain service."""

    def analyze(self, context: RiskContext, findings: tuple[RuleFinding, ...]) -> InteractionRisk:
        if not context.neighbor_zones:
            return InteractionRisk(score=0.0, topology_unavailable=context.quality.topology_unavailable)

        this_zone_hazard = _this_zone_has_propagating_hazard(findings)
        propagation_paths: list[PropagationStep] = []
        contributing_types: list[str] = []
        explanations: list[str] = []
        remaining = 1.0

        for neighbor in context.neighbor_zones:
            relationship_relevant = neighbor.relationship_type in _PROPAGATING_RELATIONSHIPS
            neighbor_elevated = neighbor.neighbor_state in _ELEVATED_NEIGHBOR_STATES

            if not relationship_relevant:
                # No modeled pathway for risk to travel through — an
                # "adjacent" neighbor with no shared system is exactly
                # the master prompt §8 "no artificial cascade risk" case.
                continue
            if not (this_zone_hazard or neighbor_elevated):
                continue

            step = PropagationStep(
                from_zone_id=context.zone_id,
                to_zone_id=neighbor.neighbor_zone_id,
                relationship_type=neighbor.relationship_type,
                neighbor_state=neighbor.neighbor_state,
            )
            propagation_paths.append(step)
            contributing_types.append(neighbor.relationship_type)

            if this_zone_hazard and neighbor_elevated:
                # Both halves of the master prompt's worked example are
                # present in one hop: this zone has a propagating hazard
                # *and* the connected neighbor is already elevated.
                contribution = 0.75
                explanations.append(
                    f"Zone {context.zone_id} has an active hazard and is "
                    f"{neighbor.relationship_type} zone {neighbor.neighbor_zone_id}, "
                    f"which is already in state '{neighbor.neighbor_state}' — "
                    "combined risk exceeds either zone's local score alone."
                )
            elif this_zone_hazard:
                contribution = 0.35
                explanations.append(
                    f"Zone {context.zone_id} has an active hazard and is "
                    f"{neighbor.relationship_type} zone {neighbor.neighbor_zone_id}; "
                    f"{neighbor.neighbor_zone_id}'s current state is not yet elevated, "
                    "so this is a lower-confidence propagation risk, not a confirmed one."
                )
            else:  # neighbor_elevated only
                contribution = 0.35
                explanations.append(
                    f"Zone {neighbor.neighbor_zone_id} is already in state "
                    f"'{neighbor.neighbor_state}' and is {neighbor.relationship_type} "
                    f"zone {context.zone_id}, which has no active hazard of its own yet."
                )

            remaining *= 1.0 - contribution

        score = (1.0 - remaining) * 100.0 if propagation_paths else 0.0

        return InteractionRisk(
            score=round(score, 2),
            propagation_paths=tuple(propagation_paths),
            contributing_relationship_types=tuple(dict.fromkeys(contributing_types)),
            explanation=tuple(explanations),
            topology_unavailable=context.quality.topology_unavailable,
        )
