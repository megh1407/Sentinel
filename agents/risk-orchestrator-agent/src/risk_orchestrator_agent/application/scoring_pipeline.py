"""application/scoring_pipeline.py — orchestrates the fixed pipeline
order (Phase 2.1 §4.2): ContextBuilder → CorrelationEngine → RuleEngine
→ RiskScorer → DecisionEngine → ExplanationBuilder → EventPublisher.

**Scope of this implementation phase.** Per this phase's brief ("No risk
scoring or recommendations should be produced yet"), this file wires
only the first two stages of Phase 2.1 §4.2's fixed order:
`ContextBuilder` and `CorrelationEngine`. It does not construct
`RuleEngine`/`RiskScorer`/`DecisionEngine`/`ExplanationBuilder`
instances — those are added, in the same fixed order, without
restructuring anything already wired here, when the corresponding
implementation phase begins (Phase 2.1 §4.2 is not renumbered or
reordered by this partial wiring).

Still the single call site `handlers/consumers.py`'s `EventRouter`
dispatches into (Phase 3.1 §3.1's allowed-imports rule: `handlers/* →
application/*`).
"""

from __future__ import annotations

import logging
import time

from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
from risk_orchestrator_agent.domain.correlation.correlation_engine import CorrelationEngine
from risk_orchestrator_agent.domain.exceptions import ContextValidationError
from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.services.context_replay_service import ContextReplayService

logger = logging.getLogger(__name__)


class ContextPipelineMetrics:
    """Backs this phase's observability requirement (event processing
    latency, context build time, snapshot generation time,
    correlation latency)."""

    def __init__(self) -> None:
        self.context_build_time_ms_last: float = 0.0
        self.snapshot_time_ms_last: float = 0.0
        self.correlation_time_ms_last: float = 0.0
        self.cycles_total: int = 0
        self.validation_failures_total: int = 0


class OperationalContextPipeline:
    """The application-layer orchestrator for this implementation
    phase: one inbound event in, one fully-correlated `RiskContext`
    snapshot out — recorded to the replay/timeline store.

    Named distinctly from `scoring_pipeline` in prose (this phase
    produces an *Operational Context*, not a score) while remaining the
    same physical file Phase 3.1 §2 designates for pipeline
    orchestration, so Phase 5 can extend this class in place rather
    than introducing a second orchestrator.
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        correlation_engine: CorrelationEngine,
        replay_service: ContextReplayService | None = None,
    ) -> None:
        self._context_builder = context_builder
        self._correlation_engine = correlation_engine
        self._replay_service = replay_service
        self.metrics = ContextPipelineMetrics()

    async def handle(self, dto: AgentResultDTO) -> RiskContext:
        """One event, fully processed through Context Building and
        Correlation. Returns the correlated `RiskContext` snapshot.

        Raises `ContextValidationError` only when the assembled context
        would otherwise be actively misleading (Phase 2.2 §6.1) — the
        caller (`EventRouter`) treats this as a DLQ-routing signal.
        """
        t0 = time.perf_counter()
        await self._context_builder.update(dto.zone_id, dto)
        self.metrics.context_build_time_ms_last = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        try:
            snapshot = await self._context_builder.snapshot(dto.zone_id)
        except ContextValidationError:
            self.metrics.validation_failures_total += 1
            raise
        self.metrics.snapshot_time_ms_last = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        correlated = self._correlation_engine.correlate_and_attach(snapshot)
        self.metrics.correlation_time_ms_last = (time.perf_counter() - t2) * 1000

        if self._replay_service is not None:
            await self._replay_service.record(dto.zone_id, correlated)

        self.metrics.cycles_total += 1
        logger.info(
            "operational_context_cycle_complete",
            extra={
                "zone_id": dto.zone_id,
                "correlation_id": dto.correlation_id,
                "completeness": correlated.quality.completeness,
                "correlation_findings": len(correlated.correlation_findings),
            },
        )
        return correlated
