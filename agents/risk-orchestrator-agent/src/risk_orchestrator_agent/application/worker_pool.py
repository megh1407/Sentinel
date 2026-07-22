"""
Bounded concurrent-execution pool for per-zone scoring cycles (Phase 9).

Placement note: this lives in application/ (not domain/) because it is pure
orchestration-layer concurrency control — it has zero business logic and
never touches a domain model's fields, matching Phase 3.1 §4's layer
responsibility table for application/.

What this replaces: nothing. application/scoring_pipeline.py (Phase 3.1 §2)
already schedules one async task per inbound Kafka message, per zone_id
partition (ALDS §9.2). WorkerPool adds a bounded semaphore *in front of* that
scheduling so a burst of simultaneous inbound events across many zones cannot
fan out into unbounded concurrent domain-service execution within one
replica — protecting RuleEngine/RiskScorer/DecisionEngine's CPU-bound work
(Phase 2.1 §9.1) from starving the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from risk_orchestrator_agent.config.pooling import WorkerPoolConfig
from risk_orchestrator_agent.telemetry.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

T = TypeVar("T")


class WorkerPoolSaturatedError(RuntimeError):
    """Raised when the bounded queue is full — a signal to apply Kafka-level
    backpressure (Phase 2.1 §9.3), never to silently drop the cycle."""


@dataclass
class WorkerPoolStats:
    in_flight: int
    queued: int
    completed_total: int
    rejected_total: int
    timed_out_total: int


class WorkerPool:
    """
    A bounded-concurrency executor for one-scoring-cycle-per-zone tasks.

    Concurrency model (ALDS §9.1/§9.2 unchanged): still one asyncio task per
    inbound event, on the platform's single shared event loop. WorkerPool
    only adds admission control (a semaphore + bounded queue) — it never
    introduces a second thread or process pool, since the pipeline's
    CPU-bound stages are deliberately small, pure functions (Phase 2.1 §9.1),
    not the kind of workload that benefits from process-level parallelism
    within a single replica.
    """

    def __init__(self, config: WorkerPoolConfig, metrics: MetricsCollector) -> None:
        self._config = config
        self._metrics = metrics
        self._semaphore = asyncio.Semaphore(config.size)
        self._queue_depth = 0
        self._in_flight = 0
        self._completed_total = 0
        self._rejected_total = 0
        self._timed_out_total = 0
        self._lock = asyncio.Lock()

    async def submit(
        self,
        zone_id: str,
        coro_factory: Callable[[], Awaitable[T]],
    ) -> T:
        """
        Run one scoring cycle's coroutine under bounded concurrency.

        `coro_factory` is a zero-arg callable that produces the coroutine —
        not the coroutine itself — so admission control happens *before* the
        cycle's async generator machinery is even constructed, avoiding a
        "coroutine was never awaited" leak if the queue is saturated.
        """
        async with self._lock:
            if self._queue_depth >= self._config.queue_max_size:
                self._rejected_total += 1
                self._metrics.increment(
                    "risk_orchestrator.worker_pool.rejected_total",
                    labels={"zone_id": zone_id},
                )
                raise WorkerPoolSaturatedError(
                    f"WorkerPool queue full ({self._queue_depth}/"
                    f"{self._config.queue_max_size}) — apply Kafka backpressure"
                )
            self._queue_depth += 1

        try:
            async with self._semaphore:
                async with self._lock:
                    self._queue_depth -= 1
                    self._in_flight += 1
                self._metrics.gauge(
                    "risk_orchestrator.worker_pool.in_flight", self._in_flight
                )
                try:
                    return await asyncio.wait_for(
                        coro_factory(), timeout=self._config.task_timeout_s
                    )
                except asyncio.TimeoutError:
                    self._timed_out_total += 1
                    self._metrics.increment(
                        "risk_orchestrator.worker_pool.timed_out_total",
                        labels={"zone_id": zone_id},
                    )
                    logger.error(
                        "scoring cycle exceeded task_timeout_s=%.1f for zone_id=%s "
                        "— this is a defect signal (Phase 2.1 §10.1), not a "
                        "transient condition",
                        self._config.task_timeout_s,
                        zone_id,
                    )
                    raise
                finally:
                    async with self._lock:
                        self._in_flight -= 1
                        self._completed_total += 1
        finally:
            pass

    def stats(self) -> WorkerPoolStats:
        return WorkerPoolStats(
            in_flight=self._in_flight,
            queued=self._queue_depth,
            completed_total=self._completed_total,
            rejected_total=self._rejected_total,
            timed_out_total=self._timed_out_total,
        )
