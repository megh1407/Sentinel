"""
test_chaos_redelivery.py

Simulates a real crash scenario: a consumer reads a message (advancing its
read position) but crashes BEFORE committing. reset_group_read_position_to_
committed() simulates the crash's effect (in-memory read position lost,
committed offset intact -- exactly what happens when a real Kafka consumer
process dies and a new one takes over the same group_id). Proves: (1) the
message is redelivered, not lost, and (2) HelloAgent's idempotent
mark_seen() means reprocessing it causes no duplicate state.
"""
import datetime
import uuid

from hello_agent import HelloAgent
from sentinel_agent_sdk.container import build_container
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_eventbus.in_memory_transport import reset_group_read_position_to_committed
from sentinel_state import StateContainer
from sentinel_state.postgres_repositories import HelloSeenRepository


def _make_event():
    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(),
        producer_service="env-ingestion",
        producer_version="1.0.0",
        site_id="SITE-01",
        zone_id="Z-104",
        partition_key="Z-104",
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=SensorEventPayload(sensor_id="S-1", sensor_type=SensorType.GAS, value=1.0, unit="ppm", threshold_breached=False),
    )


def test_message_read_but_not_committed_is_redelivered_after_simulated_crash(redis_client, postgres_session_factory):
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    consumer_transport = InMemoryTransport(client_id="c")
    producer = EventProducer(producer_transport, schema_provider)
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)

    event = _make_event()
    EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", event)

    # Simulate a crash: manually poll the raw transport (bypassing commit)
    # to represent "the consumer read it, started processing, then died
    # before committing" -- HelloAgent never even runs on this message.
    consumer_transport.subscribe(["sensor.events.raw"], group_id="hello-agent-group")
    raw_msg = consumer_transport.poll(1.0)
    assert raw_msg is not None  # confirms the message really was read

    # The read position advanced, but nothing was committed. A crash here
    # would lose the in-memory read position on restart -- simulate that:
    reset_group_read_position_to_committed("hello-agent-group", "sensor.events.raw")

    # A FRESH consumer (representing the restarted process) subscribes to
    # the SAME group_id and should receive the SAME message again.
    fresh_consumer_transport = InMemoryTransport(client_id="c-restarted")
    fresh_consumer_transport.subscribe(["sensor.events.raw"], group_id="hello-agent-group")
    redelivered_raw = fresh_consumer_transport.poll(1.0)

    assert redelivered_raw is not None
    assert redelivered_raw.offset == raw_msg.offset  # same message, not a new one -- proves no data loss

    agent = HelloAgent()
    agent.container = build_container("HelloAgent", state, producer)
    from wire_format import decode
    instance, _ = decode(redelivered_raw.value, SensorEventV1, schema_provider.get_schema_and_id("SensorEvent", 1)[0])
    result = agent.process(instance)

    assert result is not None
    assert state.hello.was_seen(str(event.event_id)) is True
    assert state.hello_pg.was_seen(str(event.event_id)) is True


def test_reprocessing_a_redelivered_event_does_not_duplicate_postgres_state(redis_client, postgres_session_factory):
    """The heart of the chaos guarantee: even if the SAME event gets
    processed twice (which redelivery can legitimately cause), HelloAgent's
    mark_seen() is idempotent -- Postgres ends up with exactly one row, not two."""
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    producer = EventProducer(producer_transport, schema_provider)
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    agent.container = build_container("HelloAgent", state, producer)

    event = _make_event()

    result1 = agent.process(event)
    result2 = agent.process(event)  # simulated redelivery -- same event, processed twice

    assert result1 is not None
    assert result2 is not None  # HelloAgent itself doesn't dedupe at the process() level...
    # ...but the STATE it writes to is idempotent regardless:
    repo = HelloSeenRepository(postgres_session_factory)
    with repo.transaction() as session:
        from sentinel_state.postgres_repositories import HelloSeenRecord
        count = session.query(HelloSeenRecord).filter_by(event_id=str(event.event_id)).count()
    assert count == 1  # exactly one row despite two process() calls -- no duplication
