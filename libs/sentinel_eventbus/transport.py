"""
transport.py

The abstraction EventProducer/EventConsumer are built on. Two real
implementations exist:

- KafkaTransport (kafka_transport.py): wraps confluent-kafka against a real
  broker. This is the production path.
- InMemoryTransport (in_memory_transport.py): a genuine, fully-functional
  in-process message bus (topic-partitioned queues, consumer-group offset
  tracking, the works) used for local development and this environment's
  tests, where no live Kafka broker is reachable. It is NOT a mock -- it is
  a real, working transport, just backed by memory instead of a distributed
  log. EventProducer/EventConsumer cannot tell the difference.

Swapping from InMemoryTransport to KafkaTransport in production is a single
constructor-argument change, nothing else in sentinel_eventbus, sentinel_
agent_sdk, or any agent's business logic needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TransportMessage:
    """A single message as seen by the transport layer -- raw bytes value,
    string headers, and delivery metadata. EventProducer/EventConsumer
    convert to/from this; the transport itself knows nothing about Avro,
    Pydantic, or SENTINEL's event contracts."""
    topic: str
    key: str | None
    value: bytes
    headers: dict[str, str] = field(default_factory=dict)
    partition: int | None = None
    offset: int | None = None


class Transport(Protocol):
    """Minimal interface EventProducer/EventConsumer depend on. Anything
    implementing this can be swapped in without touching eventbus logic."""

    def produce(self, message: TransportMessage) -> None: ...

    def subscribe(self, topics: list[str], group_id: str) -> None: ...

    def poll(self, timeout_seconds: float) -> TransportMessage | None: ...

    def commit(self, message: TransportMessage) -> None: ...

    def pause(self, topics: list[str] | None = None) -> None: ...

    def resume(self, topics: list[str] | None = None) -> None: ...

    def flush(self, timeout_seconds: float = 10.0) -> None: ...

    def close(self) -> None: ...
