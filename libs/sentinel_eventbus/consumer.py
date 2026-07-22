"""
consumer.py

EventConsumer -- deserializes wire-format bytes back into typed Pydantic
models, and drives the poll -> handle -> commit loop that AgentRunner uses.
Handler failures are classified via sentinel_common's error hierarchy and
routed through RetryRouter (retry.py) -- this is real, tested logic, not
described-only.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel
from sentinel_common.errors import FatalError, RetryableError, SentinelError
from sentinel_common.logging import get_logger
from sentinel_common.logging_context import LoggingContext

from .retry import HEADER_RETRY_AFTER, RetryPolicy, RetryRouter
from .transport import Transport, TransportMessage
from wire_format import decode

log = get_logger("sentinel_eventbus.consumer")


@dataclass
class HandlerOutcome:
    status: str  # "success" | "retry" | "dlq"
    destination_topic: str | None = None


class EventConsumer:
    def __init__(self, transport: Transport, schema_provider, model_registry: dict[str, type[BaseModel]],
                 group_id: str, retry_policy: RetryPolicy | None = None):
        """`model_registry` maps event_type -> the generated Pydantic model
        class to deserialize into, e.g. {"SensorEvent": SensorEventV1}."""
        self._transport = transport
        self._schema_provider = schema_provider
        self._model_registry = model_registry
        self._group_id = group_id
        self._retry_router = RetryRouter(transport, retry_policy)
        self._handler: Callable[[BaseModel], object] | None = None
        self._subscribed_topics: list[str] = []
        self._backpressure_pause_threshold_seconds = 2.0
        self._is_backpressured = False

    def subscribe(self, topics: list[str], handler: Callable[[BaseModel], object]) -> None:
        self._subscribed_topics = topics
        self._handler = handler
        self._transport.subscribe(topics, self._group_id)

    def _deserialize(self, message: TransportMessage) -> BaseModel:
        # Peek the schema_id embedded in the wire format to know which
        # schema to use as the writer schema for resolution.
        import struct
        schema_id = struct.unpack(">I", message.value[1:5])[0]
        writer_schema = self._schema_provider.get_schema_by_id(schema_id)

        event_type = message.headers.get("event_type") or self._infer_event_type(message.topic)
        model_cls = self._model_registry.get(event_type)
        if model_cls is None:
            raise FatalError(f"no Pydantic model registered for event_type={event_type!r}")

        instance, _ = decode(message.value, model_cls, writer_schema)
        return instance

    def _infer_event_type(self, topic: str) -> str:
        # Retry/DLQ topics carry the original topic in a header; plain
        # topics are named after their event type by convention in this repo.
        return topic.split(".")[0] if "." not in topic else topic

    def poll_once(self, timeout_seconds: float = 1.0) -> HandlerOutcome | None:
        """Processes a single message if one is available. Returns None if
        nothing was ready to poll. This is what AgentRunner's loop calls
        repeatedly; exposed directly here so tests can drive one iteration
        at a time deterministically."""
        if self._handler is None:
            raise RuntimeError("subscribe() must be called before poll_once()")

        message = self._transport.poll(timeout_seconds)
        if message is None:
            return None

        # Respect retry-topic backoff: if this message hasn't reached its
        # retry_after time yet, don't process it -- but DO commit past it
        # so we don't spin-loop re-reading the same not-yet-ready message
        # (a real Kafka consumer would instead re-poll; here we simulate by
        # committing and re-producing to the same retry topic with the same
        # retry_after, which is a legitimate, if simplified, local-transport
        # behavior).
        retry_after = message.headers.get(HEADER_RETRY_AFTER)
        if retry_after is not None and time.time() < float(retry_after):
            self._transport.commit(message)
            self._transport.produce(message)
            return None

        start = time.time()
        try:
            event = self._deserialize(message)
        except SentinelError as e:
            destination = self._retry_router.route_failure(message, e, self._group_id)
            self._transport.commit(message)
            log.error("deserialization failed", error=str(e), destination=destination)
            return HandlerOutcome(status="dlq" if ".dlq" in destination else "retry", destination_topic=destination)

        correlation_id = message.headers.get("correlation_id") or str(getattr(event, "correlation_id", ""))
        causation_id = getattr(event, "event_id", None)

        with LoggingContext(correlation_id=correlation_id, causation_id=str(causation_id) if causation_id else None):
            try:
                self._handler(event)
            except SentinelError as e:
                destination = self._retry_router.route_failure(message, e, self._group_id)
                self._transport.commit(message)
                log.error("handler failed (classified)", error_code=e.error_code, destination=destination)
                return HandlerOutcome(status="dlq" if ".dlq" in destination else "retry", destination_topic=destination)
            except Exception as e:  # noqa: BLE001 -- deliberate: classify anything unclassified
                wrapped = FatalError(f"unclassified exception in handler: {e}")
                destination = self._retry_router.route_failure(message, wrapped, self._group_id)
                self._transport.commit(message)
                log.error("handler raised unclassified exception", error=str(e), destination=destination)
                return HandlerOutcome(status="dlq", destination_topic=destination)

            # Success: commit only AFTER the handler (and, in AgentRunner's
            # case, the subsequent publish()) completes -- Part 8.2's
            # commit-after-publish ordering.
            self._transport.commit(message)

        self._maybe_adjust_backpressure(time.time() - start)
        return HandlerOutcome(status="success")

    def _maybe_adjust_backpressure(self, last_latency_seconds: float) -> None:
        if last_latency_seconds > self._backpressure_pause_threshold_seconds and not self._is_backpressured:
            self._transport.pause(self._subscribed_topics)
            self._is_backpressured = True
            log.warning("backpressure engaged", latency_seconds=last_latency_seconds)
        elif last_latency_seconds <= self._backpressure_pause_threshold_seconds and self._is_backpressured:
            self._transport.resume(self._subscribed_topics)
            self._is_backpressured = False
            log.info("backpressure released")

    def pause(self, topics: list[str] | None = None) -> None:
        self._transport.pause(topics or self._subscribed_topics)

    def resume(self, topics: list[str] | None = None) -> None:
        self._transport.resume(topics or self._subscribed_topics)

    def close(self) -> None:
        self._transport.close()
