"""
Performance profiling utilities for the Risk Orchestrator (Phase 9).

This module is purely an *observation* layer over the pipeline stages already
defined in application/scoring_pipeline.py (Phase 3.1) — it introduces no new
business logic and never changes a stage's output, only measures it.

Every budget asserted against here is quoted, not invented: Phase 1 §9.9,
Phase 2.2 §13.1, Phase 2.3 §14.1, Phase 2.4 §13.1.
"""

from __future__ import annotations

import gc
import time
import tracemalloc
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from risk_orchestrator_agent.telemetry.metrics_collector import MetricsCollector

# Stage budgets, in milliseconds — sourced from the architecture docs, never
# redefined here. Kept as constants (not magic numbers, CSEGS §2.7) so a
# budget breach is always traceable to a named source.
STAGE_BUDGETS_MS: dict[str, int] = {
    "context_builder": 150,       # Phase 2.2 §13.1
    "correlation_engine": 150,    # Phase 2.3 §14.1
    "rule_engine": 300,           # Phase 2.3 §14.1
    "risk_scorer": 200,           # Phase 2.1 §9.9
    "decision_engine": 100,       # Phase 2.4 §13.1
    "explanation_builder": 300,   # Phase 2.1 §9.9
    "publish": 300,               # Phase 2.1 §9.9 (acks=all round trip)
}
TOTAL_CYCLE_BUDGET_MS = 1500  # Phase 1 §9.1


@dataclass(frozen=True)
class StageProfile:
    """One stage's measured cost for a single scoring cycle."""

    stage: str
    duration_ms: float
    budget_ms: int
    breached: bool
    gc_collections: int
    peak_memory_bytes: int | None = None


@dataclass
class CycleProfile:
    """The full per-cycle profile — one instance per zone, per event."""

    zone_id: str
    correlation_id: str
    stages: list[StageProfile] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> float:
        return sum(s.duration_ms for s in self.stages)

    @property
    def total_breached(self) -> bool:
        return self.total_duration_ms > TOTAL_CYCLE_BUDGET_MS

    @property
    def breached_stages(self) -> list[str]:
        return [s.stage for s in self.stages if s.breached]


class StageProfiler:
    """
    Wraps one pipeline stage's execution to measure wall-clock latency,
    GC activity, and (optionally, sampled) peak memory — without altering
    control flow or swallowing exceptions from the wrapped stage.

    Usage (inside application/scoring_pipeline.py — not modified here):

        async with stage_profiler.measure("rule_engine") as prof:
            findings = await rule_engine.evaluate(correlations, rule_set)
        cycle_profile.stages.append(prof.result)
    """

    def __init__(
        self,
        metrics: MetricsCollector,
        *,
        zone_id: str,
        correlation_id: str,
        sample_memory: bool = False,
    ) -> None:
        self._metrics = metrics
        self._zone_id = zone_id
        self._correlation_id = correlation_id
        self._sample_memory = sample_memory

    @asynccontextmanager
    async def measure(self, stage: str) -> AsyncIterator["_StageMeasurement"]:
        budget = STAGE_BUDGETS_MS.get(stage)
        if budget is None:
            raise ValueError(
                f"Unknown pipeline stage '{stage}' — add it to STAGE_BUDGETS_MS "
                "only if a predecessor architecture document defines its budget."
            )

        gc_before = sum(gc.get_count())
        if self._sample_memory and not tracemalloc.is_tracing():
            tracemalloc.start()

        measurement = _StageMeasurement()
        start = time.perf_counter()
        try:
            yield measurement
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            gc_after = sum(gc.get_count())
            peak = None
            if self._sample_memory:
                _, peak = tracemalloc.get_traced_memory()

            breached = duration_ms > budget
            measurement.result = StageProfile(
                stage=stage,
                duration_ms=duration_ms,
                budget_ms=budget,
                breached=breached,
                gc_collections=max(0, gc_after - gc_before),
                peak_memory_bytes=peak,
            )

            self._metrics.observe(
                "risk_orchestrator.stage_latency_ms",
                duration_ms,
                labels={"stage": stage, "zone_id": self._zone_id},
            )
            if breached:
                self._metrics.increment(
                    "risk_orchestrator.stage_budget_breached_total",
                    labels={"stage": stage},
                )


class _StageMeasurement:
    """Mutable holder populated by StageProfiler.measure on exit."""

    result: StageProfile | None = None


def build_cycle_report(profiles: list[CycleProfile]) -> dict:
    """
    Aggregate a batch of CycleProfile objects (e.g., from a load-test run,
    Section 7 of Phase 9) into a reproducible benchmark report.

    This is deliberately a pure function over already-collected data — it
    performs no I/O and produces the same report for the same input, matching
    the platform's determinism-by-default convention (Phase 2.1 §1.5) even
    for tooling that sits outside the scoring pipeline itself.
    """
    if not profiles:
        return {"cycles": 0}

    per_stage: dict[str, list[float]] = {}
    for cycle in profiles:
        for stage in cycle.stages:
            per_stage.setdefault(stage.stage, []).append(stage.duration_ms)

    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        k = (len(ordered) - 1) * pct
        f, c = int(k), min(int(k) + 1, len(ordered) - 1)
        if f == c:
            return ordered[f]
        return ordered[f] + (ordered[c] - ordered[f]) * (k - f)

    totals = [c.total_duration_ms for c in profiles]
    return {
        "cycles": len(profiles),
        "total_cycle_ms": {
            "p50": _percentile(totals, 0.50),
            "p95": _percentile(totals, 0.95),
            "p99": _percentile(totals, 0.99),
            "max": max(totals),
            "budget_ms": TOTAL_CYCLE_BUDGET_MS,
            "breach_rate": sum(1 for c in profiles if c.total_breached) / len(profiles),
        },
        "stages": {
            stage: {
                "p50": _percentile(vals, 0.50),
                "p95": _percentile(vals, 0.95),
                "p99": _percentile(vals, 0.99),
                "max": max(vals),
                "budget_ms": STAGE_BUDGETS_MS[stage],
                "breach_rate": sum(1 for v in vals if v > STAGE_BUDGETS_MS[stage]) / len(vals),
            }
            for stage, vals in per_stage.items()
        },
    }
