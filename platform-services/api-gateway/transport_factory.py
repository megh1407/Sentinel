"""transport_factory.py -- one switch between the two REAL transports.

Both InMemoryTransport and KafkaTransport implement the same Transport
protocol (libs/sentinel_eventbus/transport.py), so EventProducer/EventConsumer
cannot tell them apart. This factory is the single, explicit place that
chooses which one every agent/consumer/producer in this gateway process uses:

    SENTINEL_TRANSPORT=memory  (default) -> InMemoryTransport (in-process bus)
    SENTINEL_TRANSPORT=kafka             -> KafkaTransport against
                                            KAFKA_BOOTSTRAP_SERVERS
                                            (default localhost:9092)

Keeping the default at `memory` means nothing that already works changes
unless you opt in; setting it to `kafka` runs the identical pipeline over the
real broker in scripts/dev-env with no other code change -- exactly the
"one-line constructor swap" the repo's own docker-compose comment promised.
"""
from __future__ import annotations

import os


def transport_kind() -> str:
    return os.environ.get("SENTINEL_TRANSPORT", "memory").lower()


# Every topic a consumer in this process subscribes to. With real Kafka a
# consumer that subscribes before the topic exists dies with
# UNKNOWN_TOPIC_OR_PART (auto-create only fires on first PRODUCE), so these
# must be created up front. DLQ twins are included because the retry router
# produces to <topic>.dlq on handler failure.
_CORE_TOPICS = [
    "sentinel.sensor.events.v1",
    "sentinel.worker.events.v1",
    "sentinel.permit.events.v1",
    "sentinel.zone.state.v1",
    "sentinel.environment.analysis.v1",
    "sentinel.permit.analysis.v1",
    "sentinel.worker.analysis.v1",
]
_ALL_TOPICS = _CORE_TOPICS + [t + ".dlq" for t in _CORE_TOPICS]


def ensure_topics(timeout: float = 20.0) -> None:
    """Idempotently create every topic this process consumes, at RF=1 (the
    single-node dev broker). No-op unless SENTINEL_TRANSPORT=kafka."""
    if transport_kind() != "kafka":
        return
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")})
    existing = set(admin.list_topics(timeout=timeout).topics)
    to_create = [NewTopic(t, num_partitions=1, replication_factor=1) for t in _ALL_TOPICS if t not in existing]
    if not to_create:
        return
    futures = admin.create_topics(to_create)
    for topic, fut in futures.items():
        try:
            fut.result(timeout=timeout)
        except Exception as exc:  # noqa: BLE001 -- "already exists" races are fine
            if "already exists" not in str(exc).lower():
                raise


def make_transport(client_id: str):
    if transport_kind() == "kafka":
        from sentinel_eventbus import KafkaTransport

        return KafkaTransport(
            bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            client_id=client_id,
        )
    from sentinel_eventbus import InMemoryTransport

    return InMemoryTransport(client_id=client_id)
