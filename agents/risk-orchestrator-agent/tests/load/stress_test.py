"""
Stress testing — pushes the system beyond documented capacity to find, and
document, the actual breaking point (Phase 9 "Stress Testing"), distinct
from load_test_scenarios.py's within-SLA scenarios.

This module doesn't run traffic itself (Locust does, via
load_test_scenarios.py's SustainedHighLoadUser/BurstTrafficUser driven past
its normal spawn-rate ceiling) — it defines the *pass/fail evaluation* of a
stress run's collected metrics against the platform's degradation model
(Phase 2.1 §10.2), so "did we degrade correctly" is a checkable assertion,
not a manual read of a Grafana dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StressRunResult:
    """Aggregate signals pulled from Prometheus after a stress run — shape
    intentionally mirrors the metrics catalog already defined across
    Phase 2.1 §11 / §16 and this repo's telemetry modules, not new metrics."""

    peak_consumer_lag: int
    p99_cycle_latency_ms: float
    dlq_routed_total: int
    breaker_open_events: dict[str, int]     # per-store, e.g. {"redis": 2}
    unhandled_exceptions_total: int
    oom_kills: int
    data_corruption_detected: bool


class StressTestEvaluator:
    """
    Verifies the three-way degradation model (Phase 2.1 §10.2) held under
    stress: degrade-and-continue, isolate-and-skip, or fail-loud-and-stop —
    never a fourth, undocumented failure mode.
    """

    @staticmethod
    def evaluate(result: StressRunResult) -> list[str]:
        violations: list[str] = []

        if result.data_corruption_detected:
            violations.append(
                "CRITICAL: data corruption detected under stress — this is "
                "never an acceptable degradation mode (Phase 2.1 §10.2)"
            )

        if result.oom_kills > 0 and result.p99_cycle_latency_ms < 1_500 * 3:
            # An OOM-kill without prior, visible latency degradation means
            # the proactive-readiness-flip safety net (ALDS §6.2) did not
            # fire before the hard kill — a defect, not an acceptable
            # stress-test outcome.
            violations.append(
                "OOM-kill occurred without preceding severe latency "
                "degradation — proactive readiness flip (ALDS §6.2) likely "
                "did not trigger in time"
            )

        if result.unhandled_exceptions_total > 0:
            violations.append(
                f"{result.unhandled_exceptions_total} unhandled exception(s) "
                "escaped application/scoring_pipeline.py — per ALDS §7.1 these "
                "must be caught, logged CRITICAL, and DLQ-routed, never crash "
                "the process outright"
            )

        # A stress run SHOULD show breaker activity and DLQ routing — their
        # total absence at extreme load is itself suspicious (it would mean
        # the stress profile never actually exceeded capacity).
        if result.peak_consumer_lag > 50_000 and result.dlq_routed_total == 0 and not result.breaker_open_events:
            violations.append(
                "Consumer lag exceeded 50k with zero breaker activity and "
                "zero DLQ routing — verify the stress profile is genuinely "
                "exercising failure paths, not just running slow"
            )

        return violations

    @staticmethod
    def document_breaking_point(results_by_load_level: dict[int, StressRunResult]) -> dict:
        """
        Produces the 'documented safe operational limits' deliverable Phase 9
        requires — the highest sustained load level where zero violations
        were recorded, and the first level where any were.
        """
        safe_level = None
        first_violation_level = None
        for load_level in sorted(results_by_load_level):
            violations = StressTestEvaluator.evaluate(results_by_load_level[load_level])
            if violations and first_violation_level is None:
                first_violation_level = load_level
            if not violations:
                safe_level = load_level
        return {
            "max_verified_safe_load_events_per_sec": safe_level,
            "first_degradation_observed_at_events_per_sec": first_violation_level,
            "recommendation": (
                f"Provision capacity for no more than {safe_level} events/sec "
                "per replica-equivalent without triggering horizontal scale-out "
                "(HPA target: consumer_lag > 1000, Phase 1 §9.2)."
                if safe_level is not None
                else "No load level in this run stayed within all documented "
                "degradation guarantees — investigate before using any result "
                "from this run for capacity planning."
            ),
        }
