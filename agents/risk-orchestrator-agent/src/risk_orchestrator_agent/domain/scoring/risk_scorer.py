"""domain/scoring/risk_scorer.py — RiskScorer.

Turns `RuleFinding`s (RuleEngine's output) into a single `LocalRiskScore`
per master prompt §7 ("Local Risk"): what this zone's own facts justify,
nothing about neighbors yet (that's `cross_zone.py`).

Combination method: noisy-OR (`1 - prod(1 - w_i)`) over each finding's
`weight * confidence`, not a capped sum. Chosen deliberately over
`sum()` because a plain sum of five 0.3-weight findings would blow past
1.0 and require an arbitrary cap, silently discarding information about
just how much evidence there was; noisy-OR saturates smoothly toward
100 as independent contributing findings accumulate, without a magic
clamp, and without letting any single weak finding dominate.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.models.risk_score import LocalRiskScore
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding

_PRIORITY_MULTIPLIER = {
    "critical": 1.0,
    "high": 0.85,
    "medium": 0.6,
    "low": 0.35,
    "informational": 0.15,
}


def _combined(findings: tuple[RuleFinding, ...]) -> float:
    if not findings:
        return 0.0
    remaining = 1.0
    for finding in findings:
        multiplier = _PRIORITY_MULTIPLIER.get(finding.priority.value, 0.5)
        contribution = finding.weight * finding.confidence * multiplier
        contribution = min(1.0, max(0.0, contribution))
        remaining *= 1.0 - contribution
    return (1.0 - remaining) * 100.0


class RiskScorer:
    """Stateless domain service."""

    def score(self, context: RiskContext, findings: tuple[RuleFinding, ...]) -> LocalRiskScore:
        return LocalRiskScore(
            zone_id=context.zone_id,
            score=round(_combined(findings), 2),
            contributor_rule_ids=tuple(f.rule_id for f in findings),
            partial_weighting=context.quality.completeness < 1.0,
        )
