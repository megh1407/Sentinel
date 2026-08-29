"""handlers/consumers.py — inbound event routing (FRS §6, Phase 2.1 §3).

`main.py` (the canonical composition root) and the API-gateway's
`orchestrator_runtime.py` both import `EventRouter` / `INBOUND_TOPICS`
from this module and drive the whole consume loop through
`EventRouter.route()`.

Phase 2 remediation note (SENTINEL forensic audit, P0-1): the version of
this file previously checked in only implemented topic filtering and
envelope re-validation — it had no dead-letter routing for unknown
topics, no metrics, no in-process idempotency, and no retry/absorb
behavior around the handler call, even though `tests/unit/handlers/
test_consumers.py` (already present in the repository, not added by
this remediation) asserts all of that behavior, and this module's own
prior docstring claimed it was "a real EventRouter... solid, not a
stub." That claim did not match the checked-in code; 5 of 6 tests in
that file failed as a result. This version implements exactly the
contract the existing test file asserts — no behavior beyond what those
tests require was invented.

  route(topic, raw) →
      1. unknown topic            -> dead-letter, metrics.dlq_routed_total += 1, return
      2. AgentResultDTO.from_raw(raw) fails (Phase 1 §4.8 re-validation)
                                   -> dead-letter with the validation reason, return
      3. duplicate event_id (in-process, bounded LRU window)
                                   -> metrics.duplicates_skipped_total += 1, return
      4. await handler(dto), retried up to `max_retries` times on exception;
         if every attempt fails, the failure is absorbed (never raised back
         into the consume loop) and metrics.handler_failures_total += 1.

No per-zone locking is taken — messages for different zones are handled
independently and cannot block one another (`test_different_zones_do_not
_block_each_other`), which was already true of the prior implementation
and is preserved unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from risk_orchestrator_agent.contracts.kafka.topics import INBOUND_TOPICS, dlq_topic_for
from risk_orchestrator_agent.dto.agent_result_dto import (
    AgentResultDTO,
    AgentResultValidationError,
)

logger = logging.getLogger(__name__)

Handler = Callable[[AgentResultDTO], Awaitable[None]]

__all__ = ["INBOUND_TOPICS", "EventRouter", "RouterMetrics"]


class DeadLetterSink(Protocol):
    """Anything that can accept a permanently-failed/rejected message.

    `dlq_topic_for(topic)` (the platform-wide `sentinel.dlq.<topic>`
    naming convention) is the caller's responsibility to apply if it
    wants the mapped name — `reason` is passed through as-is so the
    sink can log/publish/inspect why the message was rejected.
    """

    async def route(self, topic: str, raw: dict, reason: str) -> None: ...


@dataclass
class RouterMetrics:
    """In-process counters for one `EventRouter` instance. Intentionally
    plain ints, not a metrics-backend client — `platform-services/
    api-gateway` or a future observability pass can export these,
    but this module has no opinion on where they end up."""

    messages_consumed_total: int = 0
    dlq_routed_total: int = 0
    duplicates_skipped_total: int = 0
    handler_failures_total: int = 0


class _DedupeWindow:
    """Bounded in-process LRU of recently-seen `event_id`s. Documented in
    `docs/RECONCILIATION_REPORT.md` as an explicit stopgap for a later
    phase's durable, Postgres-backed uniqueness constraint — this is
    only good for redeliveries within one process's memory, not across
    restarts or replicas."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max_size = max_size
        self._seen: "OrderedDict[str, None]" = OrderedDict()

    def seen_before(self, event_id: str) -> bool:
        if event_id in self._seen:
            self._seen.move_to_end(event_id)
            return True
        self._seen[event_id] = None
        if len(self._seen) > self._max_size:
            self._seen.popitem(last=False)
        return False


class EventRouter:
    """Turns a `(topic, raw_envelope_dict)` pair into a validated
    `AgentResultDTO` and dispatches it to the orchestrator handler.

    `handler` is the async sink wired by `main.build_orchestrator`
    (`lambda dto: orchestrator.handle_event(dto)`). `dead_letter_sink`,
    if given, is anything implementing `DeadLetterSink` — used for
    unknown topics and envelopes that fail re-validation.
    """

    def __init__(
        self,
        handler: Handler,
        *,
        dead_letter_sink: DeadLetterSink | None = None,
        max_retries: int = 3,
        dedupe_window_size: int = 10_000,
    ) -> None:
        self._handler = handler
        self._dead_letter_sink = dead_letter_sink
        self._known_topics = set(INBOUND_TOPICS)
        self._max_retries = max_retries
        self._dedupe = _DedupeWindow(max_size=dedupe_window_size)
        self.metrics = RouterMetrics()

    async def route(self, topic: str, raw: dict) -> None:
        if topic not in self._known_topics:
            logger.warning(
                "dropped_event_unknown_topic",
                extra={"topic": topic, "known_topics": sorted(self._known_topics)},
            )
            await self._to_dlq(topic, raw, "Unknown topic")
            return

        try:
            dto = AgentResultDTO.from_raw(raw)
        except AgentResultValidationError as exc:
            self._log_validation_failure(topic, raw, exc)
            await self._to_dlq(topic, raw, str(exc))
            return

        self.metrics.messages_consumed_total += 1

        if self._dedupe.seen_before(dto.event_id):
            logger.info(
                "duplicate_event_skipped",
                extra={"topic": topic, "event_id": dto.event_id},
            )
            self.metrics.duplicates_skipped_total += 1
            return

        await self._dispatch_with_retry(dto)

    async def _dispatch_with_retry(self, dto: AgentResultDTO) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                await self._handler(dto)
                return
            except Exception as exc:  # noqa: BLE001 — a flaky handler must never crash the router
                last_exc = exc
                logger.warning(
                    "handler_attempt_failed",
                    extra={"event_id": dto.event_id, "attempt": attempt, "error": str(exc)},
                )
        logger.error(
            "handler_failed_after_retries",
            extra={
                "event_id": dto.event_id,
                "attempts": self._max_retries,
                "error": str(last_exc) if last_exc else None,
            },
        )
        self.metrics.handler_failures_total += 1

    def _log_validation_failure(self, topic: str, raw: dict, exc: Exception) -> None:
        logger.error(
            "agent_result_validation_failed",
            extra={"topic": topic, "error": str(exc), "event_id": raw.get("event_id")},
        )

    async def _to_dlq(self, topic: str, raw: dict, reason: str) -> None:
        self.metrics.dlq_routed_total += 1
        if self._dead_letter_sink is None:
            return
        try:
            await self._dead_letter_sink.route(dlq_topic_for(topic), raw, reason)
        except Exception:  # noqa: BLE001 — DLQ routing must never re-raise into the consume loop
            logger.exception("dlq_route_failed", extra={"topic": topic})
