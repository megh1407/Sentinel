"""
Batch-write coordinator for non-critical-path persistence (Phase 9).

Scope, precisely: this batches only the writes the architecture already
classifies as fire-and-forget / asynchronous — AuditManager records
(Phase 2.1 §3.11) and MetricsCollector export (Phase 2.1 §3.14). It never
batches the synchronous PostgreSQL transaction in the PostgreSQL Integration
design §5.1 (risk_assessments/rule_findings/decisions/audit_events), because
that transaction's atomicity is the whole point (§5.2) — batching across
independent Kafka events there would violate "a RiskAssessment is never
visible without its rule_findings" on a per-event basis.

Event ordering: batches never reorder writes for the same zone_id — the
underlying queue is FIFO per zone, matching Phase 2.2 §9.4's ordering rule.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class BatchConfig:
    max_batch_size: int = 100
    max_wait_ms: int = 200         # flush latency ceiling — audit writes are
                                    # not on the 1,500ms critical path but
                                    # still shouldn't accumulate indefinitely
    max_queue_size: int = 5000


class BatchProcessor(Generic[T]):
    """
    Accumulates items keyed by zone_id and flushes them as a single batched
    write once `max_batch_size` is reached or `max_wait_ms` elapses,
    whichever comes first — the standard micro-batching pattern, applied
    only to the fire-and-forget writes named above.
    """

    def __init__(
        self,
        config: BatchConfig,
        flush_fn: Callable[[list[T]], Awaitable[None]],
        *,
        name: str,
    ) -> None:
        self._config = config
        self._flush_fn = flush_fn
        self._name = name
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=config.max_queue_size)
        self._buffer: list[T] = []
        self._flush_task: asyncio.Task | None = None
        self._closed = False

    async def start(self) -> None:
        self._flush_task = asyncio.create_task(self._run(), name=f"batch-{self._name}")

    async def stop(self) -> None:
        """Graceful drain — awaited during ALDS §8's shutdown sequence, after
        in-flight scoring cycles complete but before store connections close."""
        self._closed = True
        if self._flush_task:
            await self._flush_task
        if self._buffer:
            await self._flush_fn(self._buffer)
            self._buffer = []

    async def enqueue(self, item: T) -> None:
        if self._closed:
            raise RuntimeError(f"BatchProcessor[{self._name}] is closed — cannot enqueue")
        await self._queue.put(item)

    async def _run(self) -> None:
        window_start = time.monotonic()
        while not self._closed or not self._queue.empty():
            timeout = max(0.0, self._config.max_wait_ms / 1000 - (time.monotonic() - window_start))
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout or 0.001)
                self._buffer.append(item)
            except asyncio.TimeoutError:
                pass

            elapsed_ms = (time.monotonic() - window_start) * 1000
            if len(self._buffer) >= self._config.max_batch_size or (
                self._buffer and elapsed_ms >= self._config.max_wait_ms
            ):
                batch, self._buffer = self._buffer, []
                window_start = time.monotonic()
                try:
                    await self._flush_fn(batch)
                except Exception:
                    logger.exception(
                        "BatchProcessor[%s] flush failed for a batch of %d items — "
                        "retry policy is the responsibility of flush_fn's own "
                        "repository call (Phase 2.1 §10.1), not this scheduler",
                        self._name,
                        len(batch),
                    )
