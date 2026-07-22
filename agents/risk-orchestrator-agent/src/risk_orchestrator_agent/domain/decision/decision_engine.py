"""domain/decision/decision_engine.py — DecisionEngine.

The system-level decision authority (master prompt §13): reconciles
`LocalRiskScore` and `InteractionRisk` into one `GlobalRiskScore`, then
classifies severity/decision category from it. No agent, RuleEngine
finding, or correlation result overrides what comes out of here — this
is the one place in the pipeline that produces the final answer.

Combination is noisy-OR again (`1 - (1-local)(1-interaction)`), for the
same reason `risk_scorer.py` uses it internally: it guarantees
`global >= local` always, `global > local` strictly whenever
`interaction > 0` (master prompt §8's "Global Risk > Maximum Individual
Zone Risk" requirement for a genuine cross-zone interaction), and
`global == local` exactly when there is no interaction at all (§8's "no
artificial cascade risk" requirement) — a plain sum would violate the
first guarantee once local+interaction exceeded 100, and would violate
the "traceable, not double-counted" requirement in §11 the moment both
terms drew from overlapping evidence.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.enums import RISK_LEVEL_ORDER, DecisionCategory, RiskLevel
from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.models.risk_score import GlobalRiskScore, InteractionRisk, LocalRiskScore
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding

# (upper_bound_exclusive, RiskLevel, DecisionCategory) — checked in order,
# first match wins. Bands are a starting point, not a claimed regulatory
# standard; tune via config in a later phase rather than hardcoding a
# different table per site.
_BANDS: tuple[tuple[float, RiskLevel, DecisionCategory], ...] = (
    (15.0, RiskLevel.NEGLIGIBLE, DecisionCategory.SAFE),
    (35.0, RiskLevel.LOW, DecisionCategory.SAFE),
    (55.0, RiskLevel.MODERATE, DecisionCategory.WARNING),
    (70.0, RiskLevel.HIGH, DecisionCategory.HIGH_RISK),
    (85.0, RiskLevel.CRITICAL, DecisionCategory.CRITICAL_RISK),
    (float("inf"), RiskLevel.CATASTROPHIC, DecisionCategory.EMERGENCY),
)


def _classify(score: float) -> tuple[RiskLevel, DecisionCategory]:
    for upper, level, category in _BANDS:
        if score < upper:
            return level, category
    return _BANDS[-1][1], _BANDS[-1][2]  # unreachable (last bound is inf), kept for safety


def classify_score(score: float) -> RiskLevel:
    """Public wrapper around the same severity bands `DecisionEngine`
    uses internally, for callers (e.g. `domain/decision/site_synthesizer.
    py`) that need to classify a score without going through the full
    `synthesize()`/`classify()` per-zone flow."""
    level, _ = _classify(score)
    return level


def _combine(local: float, interaction: float) -> float:
    local_frac = min(1.0, max(0.0, local / 100.0))
    interaction_frac = min(1.0, max(0.0, interaction / 100.0))
    combined = 1.0 - (1.0 - local_frac) * (1.0 - interaction_frac)
    return round(combined * 100.0, 2)


class DecisionEngine:
    """Stateless domain service."""

    def synthesize(
        self,
        context: RiskContext,
        local: LocalRiskScore,
        interaction: InteractionRisk,
    ) -> GlobalRiskScore:
        value = _combine(local.score, interaction.score)
        return GlobalRiskScore(
            zone_id=context.zone_id,
            value=value,
            local=local,
            interaction=interaction,
            analysis_completeness="partial" if context.quality.missing_domains else "complete",
            missing_domains=context.quality.missing_domains,
        )

    def classify(
        self,
        global_score: GlobalRiskScore,
        *,
        findings: tuple[RuleFinding, ...],
        previous_severity: str | None = None,
    ) -> tuple[RiskLevel, DecisionCategory, bool, bool]:
        """Returns (severity, decision_category, escalation_required,
        manual_review_required)."""
        severity, category = _classify(global_score.value)

        # Evacuation supersedes the score-band category when any rule
        # finding explicitly flags it — a discrete safety signal from
        # RuleEngine is never diluted by averaging it into a continuous
        # score (master prompt §13: agents/rules don't override the
        # global decision, but a hard finding like this is exactly what
        # the global decision must directly incorporate, not discard).
        if any(f.rule_id == "sensor.evacuation_required" for f in findings):
            category = DecisionCategory.EVACUATION_RECOMMENDED

        escalation_required = severity in (RiskLevel.CRITICAL, RiskLevel.CATASTROPHIC) or (
            category == DecisionCategory.EVACUATION_RECOMMENDED
        )

        manual_review_required = (
            global_score.analysis_completeness == "partial"
            and severity in (RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.CATASTROPHIC)
        ) or global_score.interaction.topology_unavailable

        if previous_severity is not None and previous_severity != severity.value:
            current_idx = RISK_LEVEL_ORDER.index(severity)
            try:
                previous_idx = RISK_LEVEL_ORDER.index(RiskLevel(previous_severity))
            except ValueError:
                previous_idx = current_idx
            if current_idx > previous_idx:
                manual_review_required = manual_review_required or (
                    current_idx - previous_idx >= 2
                )

        return severity, category, escalation_required, manual_review_required
