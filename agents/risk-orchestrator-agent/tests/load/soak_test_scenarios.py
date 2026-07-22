"""
Soak testing (Phase 9 'TESTING' section) — long-duration, moderate-load run
whose purpose is catching *slow* regressions load/stress tests are too short
to see: connection leaks, unbounded OperationalTimeline/EvidenceCollection
growth (Phase 2.2 §13.2/§18.3), gradual metrics-cardinality creep, or a
worker-pool queue that never fully drains.

Run via the same Locust harness as load_test_scenarios.py, but for a much
longer --run-time (recommended: 4-12 hours), sampling resource metrics on
an interval rather than asserting once at the end.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SoakSample:
    timestamp_s: float
    memory_bytes: int
    open_connections: dict[str, int]   # per-store
    worker_pool_queue_depth: int
    operational_timeline_avg_bytes: float


@dataclass
class SoakTestReport:
    samples: list[SoakSample] = field(default_factory=list)

    def memory_growth_rate_bytes_per_hour(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        first, last = self.samples[0], self.samples[-1]
        hours = (last.timestamp_s - first.timestamp_s) / 3600
        if hours <= 0:
            return 0.0
        return (last.memory_bytes - first.memory_bytes) / hours

    def evaluate(self) -> list[str]:
        """
        Flags a soak run as suspicious, never as a hard pass/fail — a soak
        test's job is to surface a slow trend for a human to interpret, per
        TSES §1.6's 'continuous validation' philosophy, not to gate CI.
        """
        findings: list[str] = []

        growth_rate = self.memory_growth_rate_bytes_per_hour()
        if growth_rate > 50 * 1024 * 1024:  # >50MB/hour sustained growth
            findings.append(
                f"Memory grew at {growth_rate / (1024*1024):.1f} MB/hour — "
                "investigate for a leak; RiskContext is budgeted at a few "
                "hundred KB per zone and should not accumulate (Phase 2.2 §13.2)"
            )

        if self.samples and self.samples[-1].worker_pool_queue_depth > 0:
            trailing = [s.worker_pool_queue_depth for s in self.samples[-10:]]
            if all(d > 0 for d in trailing):
                findings.append(
                    "WorkerPool queue depth never reached zero across the "
                    "trailing sample window — the pool may be persistently "
                    "under-provisioned relative to sustained load "
                    "(config/pooling.py's WorkerPoolConfig.size)"
                )

        for store in ("postgres", "redis", "neo4j"):
            if self.samples:
                counts = [s.open_connections.get(store, 0) for s in self.samples]
                if counts[-1] > counts[0] * 1.5 and counts[-1] > 10:
                    findings.append(
                        f"{store} open-connection count grew from {counts[0]} "
                        f"to {counts[-1]} over the run — possible connection leak"
                    )

        return findings


def run_soak_sample_loop(sampler, duration_s: int, interval_s: int = 300) -> SoakTestReport:
    """`sampler` is an injected callable returning a SoakSample — kept as a
    thin driver so this module has no direct infra dependency of its own."""
    report = SoakTestReport()
    start = time.monotonic()
    while time.monotonic() - start < duration_s:
        report.samples.append(sampler())
        time.sleep(interval_s)
    return report
