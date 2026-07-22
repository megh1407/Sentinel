"""handlers/consumers.py — inbound event routing (FRS §6, Phase 2.1 §3).

This module was an empty stub in the merged snapshot even though
`main.py` (the canonical composition root) and the API-gateway's
`orchestrator_runtime.py` both import `EventRouter` / `INBOUND_TOPICS`
from it and drive the whole consume loop through `EventRouter.route()`.
Implemented here to the contract those callers already assume — no new
behavior invented beyond what `AgentResultDTO.from_raw` + the
`orchestrator.handle_event` handler already define:

  route(topic, raw) →
      1. reject topics outside the six registered INBOUND_TOPICS
      2. AgentResultDTO.from_raw(raw)  (re-validates the envelope, Phase 1 §4.8)
      3. await handler(dto)            (into Orchestrator.handle_event)

A malformed envelope raises AgentResultValidationError inside from_raw;
per that class's own docstring it must be routed to the DLQ and never
propagated into domain logic. When a `dlq_producer` is supplied it is
published to `sentinel.dlq.<topic>`; otherwise the failure is logged and
swallowed so one bad message can never stall the consumer group.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from risk_orchestrator_agent.contracts.kafka.topics import INBOUND_TOPICS, dlq_topic_for
from risk_orchestrator_agent.dto.agent_result_dto import (
    AgentResultDTO,
    AgentResultValidationError,
)

logger = logging.getLogger(__name__)

Handler = Callable[[AgentResultDTO], Awaitable[None]]

__all__ = ["INBOUND_TOPICS", "EventRouter"]


class EventRouter:
    """Turns a `(topic, raw_envelope_dict)` pair into a validated
    `AgentResultDTO` and dispatches it to the orchestrator handler.

    `handler` is the async sink returned wired by `main.build_orchestrator`
    (`lambda dto: orchestrator.handle_event(dto)`). `dlq_producer`, if
    given, is anything exposing `publish(topic, payload)` — used only for
    envelopes that fail re-validation.
    """

    def __init__(self, handler: Handler, *, dlq_producer=None) -> None:
        self._handler = handler
        self._dlq_producer = dlq_producer
        self._known_topics = set(INBOUND_TOPICS)

    async def route(self, topic: str, raw: dict) -> None:
        if topic not in self._known_topics:
            logger.warning(
                "dropped_event_unknown_topic",
                extra={"topic": topic, "known_topics": sorted(self._known_topics)},
            )
            return

        try:
            dto = AgentResultDTO.from_raw(raw)
        except AgentResultValidationError as exc:
            self._to_dlq(topic, raw, exc)
            return

        await self._handler(dto)

    def _to_dlq(self, topic: str, raw: dict, exc: Exception) -> None:
        logger.error(
            "agent_result_validation_failed",
            extra={"topic": topic, "error": str(exc), "event_id": raw.get("event_id")},
        )
        if self._dlq_producer is not None:
            try:
                self._dlq_producer.publish(dlq_topic_for(topic), raw)
            except Exception:  # noqa: BLE001 — DLQ publish must never re-raise into the consume loop
                logger.exception("dlq_publish_failed", extra={"topic": topic})
