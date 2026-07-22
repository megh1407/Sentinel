"""domain/correlation/correlation_engine.py — CorrelationEngine
(Phase 2.3 §2, §4, §6), scoped for this implementation phase to
relationship discovery only.

Correlation is evidence, not judgment (Phase 2.3 §1.4): this engine
never decides that something is *risky* — only that two or more facts
are *related*, with what strength and what evidence. Rule evaluation
(RuleEngine) is out of scope for this phase.

Deliberately has no dependency on `RepositoryManager`/concrete adapters
(Phase 2.1 §5.2) beyond the conditional `GraphRepositoryPort`, injected.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.correlation import correlation_types
from risk_orchestrator_agent.domain.models.correlation_finding import CorrelationFinding
from risk_orchestrator_agent.domain.models.risk_context import RiskContext

# Concurrent-safe: each evaluator reads a disjoint slice of RiskContext and
# writes a disjoint CorrelationFinding subset (Phase 2.3 §14.3) — no shared
# mutable state, no locking required.
_STRUCTURAL_EVALUATORS = (
    correlation_types.worker_zone,
    correlation_types.worker_permit,
    correlation_types.worker_equipment,
    correlation_types.zone_equipment,
    correlation_types.equipment_maintenance,
    correlation_types.permit_zone,
    correlation_types.permit_equipment,
    correlation_types.environment_zone,
    correlation_types.incident_worker,
    correlation_types.incident_equipment,
    correlation_types.incident_historical,
    correlation_types.zone_neighbor_zone,
)


class CorrelationEngine:
    """Stateless domain service. Pure function of its input `RiskContext`
    (Phase 2.1 §8's idempotency contract: fully idempotent)."""

    def correlate(self, context: RiskContext) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []
        for evaluator in _STRUCTURAL_EVALUATORS:
            findings.extend(evaluator(context))
        return findings

    def correlate_and_attach(self, context: RiskContext) -> RiskContext:
        """Convenience for the pipeline: correlate, then return a new
        RiskContext snapshot carrying the findings (RiskContext otherwise
        unchanged, per its own immutability guarantee)."""
        findings = self.correlate(context)
        return context.with_correlation_findings(tuple(findings))
