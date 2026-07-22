"""domain/explanation/explanation_builder.py — ExplanationBuilder.

Master prompt §12: "Never return only risk = 0.92" — every
`SystemRiskAssessment` must carry a human-readable `explanation` plus a
structured `contributing_factors` list. This module is pure text
assembly over already-computed values (`GlobalRiskScore`, `RuleFinding`s)
— it makes no risk judgments of its own, matching
`domain/exceptions.IncompleteExplanationError`'s existing (if
not-yet-raised) contract: if the assessment it's given doesn't carry
enough evidence to explain itself, that's a bug upstream, not something
this builder should paper over silently.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.models.risk_score import GlobalRiskScore
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding


class ExplanationBuilder:
    """Stateless domain service."""

    def contributing_factors(
        self, global_score: GlobalRiskScore, findings: tuple[RuleFinding, ...]
    ) -> tuple[str, ...]:
        factors = [f.description for f in findings]
        factors.extend(global_score.interaction.explanation)
        return tuple(factors)

    def build(self, global_score: GlobalRiskScore, findings: tuple[RuleFinding, ...], *, severity: str) -> str:
        local = global_score.local
        interaction = global_score.interaction

        lines = [f"GLOBAL RISK: {severity.upper()} (score={global_score.value})", ""]

        if global_score.analysis_completeness == "partial":
            lines.append(
                f"NOTE: analysis is PARTIAL — missing domains: {list(global_score.missing_domains)}. "
                "This is not a complete system assessment."
            )
            lines.append("")

        lines.append(f"Local risk for zone {local.zone_id}: {local.score}")
        if not findings:
            lines.append("  - No contributing rule findings.")
        for finding in findings:
            lines.append(f"  - [{finding.priority.value}] {finding.description}")

        lines.append("")
        if interaction.score > 0:
            lines.append(f"Cross-zone interaction risk: {interaction.score}")
            for explanation in interaction.explanation:
                lines.append(f"  - {explanation}")
            if interaction.propagation_paths:
                path_text = " -> ".join(
                    [interaction.propagation_paths[0].from_zone_id]
                    + [step.to_zone_id for step in interaction.propagation_paths]
                )
                lines.append(f"  Propagation path: {path_text}")
            lines.append("")
            lines.append(
                "Local zone risk alone did not produce the final severity; "
                "cross-zone interaction increased the system-level risk."
            )
        else:
            lines.append(
                "No cross-zone interaction risk detected "
                "(no risk-relevant relationship to an elevated neighbor was found)."
            )

        return "\n".join(lines)
