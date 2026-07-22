"""
kafka_transport.py

The production Transport implementation, backed by confluent-kafka (which
wraps librdkafka). This is real, correct code against confluent-kafka's
actual API -- but it is NOT exercised against a live broker in this
environment (no network path to a Kafka cluster here). Treat this file as
code-reviewed, not live-verified, until it's run against
`scripts/dev-env`'s local broker or a real cluster. InMemoryTransport
(same interface) is what's actually exercised by this repo's test suite.
"""
from __future__ import annotations

from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition
from confluent_kafka.admin import AdminClient

from .transport import Transport, TransportMessage


class KafkaTransport:
    """Wraps a confluent_kafka Producer + Consumer pair behind the Transport
    protocol. One instance is used either purely as a producer or purely as
    a consumer in practice (EventProducer/EventConsumer each construct
    their own), but both code paths live here since they share connection
    config."""

    def __init__(self, bootstrap_servers: str, client_id: str,
                 security_config: dict | None = None):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._security_config = security_config or {}
        self._producer: Producer | None = None
        self._consumer: Consumer | None = None
        self._group_id: str | None = None
        self._subscribed_topics: list[str] = []

    def _producer_config(self) -> dict:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "enable.idempotence": True,  # broker-level idempotent producer, Part 4.5
            "acks": "all",
            "retries": 5,
            **self._security_config,
        }

    def _consumer_config(self, group_id: str) -> dict:
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "group.id": group_id,
            "enable.auto.commit": False,  # manual commit only, Part 4.2
            "auto.offset.reset": "earliest",
            "partition.assignment.strategy": "cooperative-sticky",  # Part 4.8
            **self._security_config,
        }

    def produce(self, message: TransportMessage) -> None:
        if self._producer is None:
            self._producer = Producer(self._producer_config())

        delivery_errors: list[Exception] = []

        def _on_delivery(err, msg):
            if err is not None:
                delivery_errors.append(KafkaException(err))

        header_list = [(k, v.encode("utf-8")) for k, v in message.headers.items()]
        self._producer.produce(
            topic=message.topic,
            key=message.key.encode("utf-8") if message.key else None,
            value=message.value,
            headers=header_list,
            callback=_on_delivery,
        )
        self._producer.poll(0)  # serve delivery callbacks without blocking
        if delivery_errors:
            raise delivery_errors[0]

    def subscribe(self, topics: list[str], group_id: str) -> None:
        self._group_id = group_id
        self._subscribed_topics = topics
        self._consumer = Consumer(self._consumer_config(group_id))
        self._consumer.subscribe(topics)

    def poll(self, timeout_seconds: float) -> TransportMessage | None:
        if self._consumer is None:
            raise RuntimeError("subscribe() must be called before poll()")
        msg = self._consumer.poll(timeout_seconds)
        if msg is None:
            return None
        if msg.error():
            raise KafkaException(msg.error())
        headers = {k: v.decode("utf-8") for k, v in (msg.headers() or [])}
        return TransportMessage(
            topic=msg.topic(),
            key=msg.key().decode("utf-8") if msg.key() else None,
            value=msg.value(),
            headers=headers,
            partition=msg.partition(),
            offset=msg.offset(),
        )

    def commit(self, message: TransportMessage) -> None:
        if self._consumer is None:
            return
        tp = TopicPartition(message.topic, message.partition, message.offset + 1)
        self._consumer.commit(offsets=[tp], asynchronous=False)

    def pause(self, topics: list[str] | None = None) -> None:
        if self._consumer is None:
            return
        assignment = self._consumer.assignment()
        target = assignment if not topics else [tp for tp in assignment if tp.topic in topics]
        self._consumer.pause(target)

    def resume(self, topics: list[str] | None = None) -> None:
        if self._consumer is None:
            return
        assignment = self._consumer.assignment()
        target = assignment if not topics else [tp for tp in assignment if tp.topic in topics]
        self._consumer.resume(target)

    def flush(self, timeout_seconds: float = 10.0) -> None:
        if self._producer is not None:
            self._producer.flush(timeout_seconds)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush(10.0)
        if self._consumer is not None:
            self._consumer.close()

    def broker_reachable(self, timeout_seconds: float = 3.0) -> bool:
        """Used by the health-check system (Part 9) -- a lightweight
        metadata fetch, not a full produce/consume round-trip."""
        try:
            admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
            admin.list_topics(timeout=timeout_seconds)
            return True
        except Exception:
            return False
