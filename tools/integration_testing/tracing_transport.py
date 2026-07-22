"""
tracing_transport.py

TracingTransport wraps a real KafkaTransport and reports every produce/
subscribe/poll/commit call to event_logger, then delegates to the real
call. It is legal to build this without touching sentinel_eventbus because
Transport is documented (transport.py's own module docstring) as a
Protocol precisely so implementations can be swapped in "without touching
eventbus logic" -- EventProducer/EventConsumer only ever call the methods
below, never KafkaTransport directly. Wrapping it is therefore
instrumentation, not a contract or business-logic change, and the real
KafkaTransport underneath is exercised exactly as production would.

One honest limitation, not worked around: KafkaTransport.produce() (see
kafka_transport.py) does not populate TransportMessage.partition/offset --
confluent-kafka's delivery report (where partition/offset become known) is
only available via the async delivery callback, which kafka_transport.py
currently discards except for errors. That means "Messages Published"
here can confirm *that* produce() succeeded (no delivery error raised) but
cannot report a real partition/offset for it -- reported as None rather
than a fabricated value. flush() (called explicitly after produce in this
wrapper, for demo purposes only) forces delivery so the error path is
exercised synchronously; it does not change what gets delivered.
Note on trace_id: producer.py's own header dict (verified by reading it) carries
`correlation_id`, `causation_id`, `event_type`, `schema_version`, retry/original-topic
headers, and an OTel `traceparent` -- never the domain `trace_id` payload field, which
only exists inside the Avro-encoded event body. Every simulator in this harness sets
its events' trace_id field equal to str(correlation_id) specifically so this wrapper
can recover a consistent join key from headers alone without needing to decode the
message body (which would mean duplicating EventConsumer's own deserialization here).
"""
from __future__ import annotations

import time

from sentinel_eventbus.transport import Transport, TransportMessage

from event_logger import StageEvent, log_stage


class TracingTransport:
    def __init__(self, real: Transport, component: str, flush_after_produce: bool = True,
                 component_by_topic: dict[str, str] | None = None):
        self._real = real
        self._component = component
        self._flush_after_produce = flush_after_produce
        # Optional: some processes (fake_data_engine_simulator.py) multiplex several
        # logical simulators over one shared transport/producer. When set, the
        # component name for a given message is looked up by topic instead of using
        # the fixed `component` passed above, so "SensorEvent Created" and its
        # corresponding "Kafka Publish" row report under the same component name.
        self._component_by_topic = component_by_topic or {}

    def _component_for(self, topic: str) -> str:
        return self._component_by_topic.get(topic, self._component)

    # -- Transport protocol, instrumented -----------------------------
    def produce(self, message: TransportMessage) -> None:
        correlation_id = message.headers.get("correlation_id")
        trace_id = correlation_id  # see module docstring
        event_type = message.headers.get("event_type")
        component = self._component_for(message.topic)
        start = time.time()
        try:
            self._real.produce(message)
            if self._flush_after_produce:
                self._real.flush(5.0)
        except Exception as e:  # noqa: BLE001
            log_stage(StageEvent(
                component=component, stage="Kafka Publish", status="failed",
                trace_id=trace_id, correlation_id=correlation_id, topic=message.topic,
                event_type=event_type, reason=f"{type(e).__name__}: {e}",
                duration_ms=(time.time() - start) * 1000,
            ))
            raise
        log_stage(StageEvent(
            component=component, stage="Kafka Publish", status="success",
            trace_id=trace_id, correlation_id=correlation_id, topic=message.topic,
            event_type=event_type, duration_ms=(time.time() - start) * 1000,
            extra={"key": message.key, "value_bytes": len(message.value)},
        ))

    def subscribe(self, topics: list[str], group_id: str) -> None:
        self._real.subscribe(topics, group_id)
        log_stage(StageEvent(
            component=self._component, stage="Kafka Subscribe", status="success",
            consumer_group=group_id, extra={"topics": topics},
        ))

    def poll(self, timeout_seconds: float) -> TransportMessage | None:
        try:
            msg = self._real.poll(timeout_seconds)
        except Exception as e:  # noqa: BLE001
            log_stage(StageEvent(
                component=self._component, stage="Kafka Poll", status="failed",
                reason=f"{type(e).__name__}: {e}",
            ))
            raise
        if msg is None:
            return None
        trace_id = msg.headers.get("correlation_id")
        correlation_id = trace_id
        event_type = msg.headers.get("event_type")
        log_stage(StageEvent(
            component=self._component, stage="Kafka Message Received", status="success",
            trace_id=trace_id, correlation_id=correlation_id, topic=msg.topic,
            partition=msg.partition, offset=msg.offset, event_type=event_type,
        ))
        return msg

    def commit(self, message: TransportMessage) -> None:
        self._real.commit(message)
        trace_id = message.headers.get("correlation_id")
        log_stage(StageEvent(
            component=self._component, stage="Kafka Offset Committed", status="success",
            trace_id=trace_id, topic=message.topic, partition=message.partition, offset=message.offset,
        ))

    def pause(self, topics: list[str] | None = None) -> None:
        self._real.pause(topics)
        log_stage(StageEvent(component=self._component, stage="Kafka Backpressure Pause", status="info",
                              extra={"topics": topics}))

    def resume(self, topics: list[str] | None = None) -> None:
        self._real.resume(topics)
        log_stage(StageEvent(component=self._component, stage="Kafka Backpressure Resume", status="info",
                              extra={"topics": topics}))

    def flush(self, timeout_seconds: float = 10.0) -> None:
        self._real.flush(timeout_seconds)

    def close(self) -> None:
        self._real.close()

    def broker_reachable(self, timeout_seconds: float = 3.0) -> bool:
        return self._real.broker_reachable(timeout_seconds)
