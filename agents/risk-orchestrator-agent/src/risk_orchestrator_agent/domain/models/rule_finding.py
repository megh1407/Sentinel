"""RuleFinding value object.

Bridges CorrelationEngine's evidence-only findings and RiskScorer's
numeric contribution: a `RuleFinding` is the first place in the pipeline
that a fact is judged, not just related (see
`domain/correlation/correlation_engine.py`'s own docstring: "Correlation
is evidence, not judgment... Judgment belongs to RuleEngine").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from risk_orchestrator_agent.domain.enums import RuleCategory, RulePriority


@dataclass(frozen=True, slots=True)
class RuleFinding:
    rule_id: str
    category: RuleCategory
    priority: RulePriority
    # Contribution to LOCAL risk, in [0, 1] — RiskScorer weights and sums
    # these; it is not itself the final score.
    weight: float
    confidence: float
    description: str
    entity_refs: tuple[str, ...] = field(default_factory=tuple)
    # finding_id(s) of the CorrelationFinding(s) this rule fired from, so
    # ExplanationBuilder can walk back to the original evidence.
    source_finding_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "weight", min(1.0, max(0.0, self.weight)))
        object.__setattr__(self, "confidence", min(1.0, max(0.0, self.confidence)))
