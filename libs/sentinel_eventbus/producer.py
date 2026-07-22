"""
producer.py

EventProducer.publish(event) -- the one method agent code (via
sentinel_agent_sdk) actually calls to send a result. Wires together:
- the Pydantic event model (from sentinel_contracts)
- its Avro schema (via schema_loader / registry_client)
- the Confluent wire format (magic byte + schema id + Avro bytes)
- standard headers (correlation_id, causation_id, retry_count,
  schema_version, trace_id) auto-populated from the active LoggingContext
  and tracing span
- the Transport (Kafka in production, in-memory here)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import BaseModel
from sentinel_common.errors import FatalError, RetryableError
from sentinel_common.logging_context import get_causation_id, get_correlation_id
from sentinel_common.tracing import inject_trace_headers

from .retry import HEADER_ORIGINAL_TOPIC, HEADER_RETRY_COUNT
from .transport import Transport, TransportMessage
from wire_format import encode


@dataclass
class PublishResult:
    topic: str
    partition: int | None
    offset: int | None
    event_id: str


class EventProducer:
    def __init__(self, transport: Transport, schema_provider):
        """`schema_provider` is any object exposing
        `get_schema_and_id(event_type: str, version: int) -> tuple[dict, int]`
        -- in production this is backed by SchemaRegistryClient; in this
        environment/tests it's backed by a local schema_loader-based
        provider (LocalSchemaProvider, defined in schema_provider.py) so
        publishing works without a live registry."""
        self._transport = transport
        self._schema_provider = schema_provider

    def publish(self, topic: str, event: BaseModel, key: str | None = None) -> PublishResult:
        event_type = getattr(event, "event_type", type(event).__name__)
        version = getattr(event, "SCHEMA_VERSION", getattr(event, "event_version", 1))

        try:
            avro_schema, schema_id = self._schema_provider.get_schema_and_id(event_type, version)
        except Exception as e:  # noqa: BLE001
            raise FatalError(f"could not resolve schema for {event_type} v{version}: {e}") from e

        try:
            wire_bytes = encode(event, avro_schema, schema_id)
        except Exception as e:  # noqa: BLE001
            raise FatalError(f"failed to serialize {event_type}: {e}") from e

        headers = {
            "correlation_id": str(getattr(event, "correlation_id", get_correlation_id() or "")),
            "causation_id": str(getattr(event, "causation_id", get_causation_id() or "") or ""),
            HEADER_RETRY_COUNT: "0",
            "schema_version": str(version),
            "event_type": event_type,
            HEADER_ORIGINAL_TOPIC: topic,
        }
        inject_trace_headers(headers)

        partition_key = key or getattr(event, "partition_key", None) or str(uuid.uuid4())

        message = TransportMessage(topic=topic, key=partition_key, value=wire_bytes, headers=headers)
        try:
            self._transport.produce(message)
        except Exception as e:  # noqa: BLE001
            raise RetryableError(f"transport failed to produce to {topic}: {e}") from e

        return PublishResult(
            topic=topic, partition=message.partition, offset=message.offset,
            event_id=str(getattr(event, "event_id", "")),
        )

    def publish_batch(self, topic: str, events: list[BaseModel], key: str | None = None) -> list[PublishResult]:
        results = []
        for event in events:
            try:
                results.append(self.publish(topic, event, key))
            except (FatalError, RetryableError) as e:
                results.append(e)  # partial-failure-safe: caller inspects each result
        return results

    def flush(self, timeout_seconds: float = 10.0) -> None:
        self._transport.flush(timeout_seconds)

    def close(self) -> None:
        self._transport.close()
