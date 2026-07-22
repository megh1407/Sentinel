"""
permit_risk_evaluator.py

Combines the outputs of PermitLifecycleValidator, PermitConditionEvaluator,
ZoneCompatibilityEvaluator, and PermitConflictEvaluator into a single
0-100 risk_score and a permit_risk_level bucket
(acceptable|elevated|high|unacceptable, matching
contracts/agent-contracts/v1/permit_analysis.schema.json's enum).

Weighting below is a deliberate, documented default -- not derived from
the frozen contracts (which specify the *shape* of risk_score, not its
formula) -- and should be reviewed by the safety domain owner before
production use, same caveat as the zone/conflict rule tables.
"""
from __future__ import annotations

_CONFLICT_SEVERITY_WEIGHT = {"blocking": 25.0, "warning": 12.0, "advisory": 4.0}
_MAX_CONFLICT_CONTRIBUTION = 45.0
_LIFECYCLE_INVALID_WEIGHT = 35.0
_MAX_ZONE_CONTRIBUTION = 40.0
_MAX_CONDITION_CONTRIBUTION = 15.0
_UNKNOWN_ZONE_DEFAULT_CONTRIBUTION = 15.0  # unknown is treated as moderately risky, never as "safe"
_ZONE_BLOCKING_INCOMPATIBILITY_PENALTY = 25.0  # zone_compatibility == False is a decisive signal on its own,
# not just a point on the continuous zone-risk curve -- a permit the Zone Agent says is outright incompatible
# with current conditions should not land in the same bucket as one that merely shares a moderately-risky zone.


class PermitRiskEvaluator:
    def calculate(
        self,
        lifecycle_valid: bool,
        zone_compatibility: bool | None,
        zone_risk_at_issuance: float | None,
        conflicts: list,
        unsatisfied_condition_ratio: float,
    ) -> tuple[float, str]:
        score = 0.0

        if not lifecycle_valid:
            score += _LIFECYCLE_INVALID_WEIGHT

        if zone_risk_at_issuance is None:
            score += _UNKNOWN_ZONE_DEFAULT_CONTRIBUTION
        else:
            score += min(_MAX_ZONE_CONTRIBUTION, (zone_risk_at_issuance / 100.0) * _MAX_ZONE_CONTRIBUTION)

        if zone_compatibility is False:
            score += _ZONE_BLOCKING_INCOMPATIBILITY_PENALTY

        conflict_contribution = sum(_CONFLICT_SEVERITY_WEIGHT.get(c.severity, 0.0) for c in conflicts)
        score += min(_MAX_CONFLICT_CONTRIBUTION, conflict_contribution)

        score += unsatisfied_condition_ratio * _MAX_CONDITION_CONTRIBUTION

        score = round(min(score, 100.0), 2)
        return score, self._bucket(score)

    @staticmethod
    def _bucket(score: float) -> str:
        if score >= 80:
            return "unacceptable"
        if score >= 55:
            return "high"
        if score >= 25:
            return "elevated"
        return "acceptable"
