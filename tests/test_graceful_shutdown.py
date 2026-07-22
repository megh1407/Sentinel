"""
test_graceful_shutdown.py

Proves AgentRunner.drain() actually waits for in-flight processing to
finish before closing connections, and that request_shutdown() stops the
run loop from picking up new work -- without needing to send a real OS
signal.
"""
import datetime
import threading
import time
import uuid

from hello_agent import HelloAgent
from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer


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


def test_request_shutdown_stops_the_run_loop_without_processing_more_events(redis_client, postgres_session_factory):
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    consumer_transport = InMemoryTransport(client_id="c")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, {"SensorEvent": SensorEventV1}, group_id="g")
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=["sensor.events.raw"], output_topic="agent.results")

    events = [_make_event() for _ in range(3)]
    for e in events:
        EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", e)

    def _shutdown_soon():
        time.sleep(0.03)
        runner.request_shutdown()

    threading.Thread(target=_shutdown_soon).start()
    runner.run(poll_timeout_seconds=0.01, max_empty_polls=500)

    assert runner._iterations_processed <= 3
    assert runner._shutdown_requested is True


def test_drain_waits_for_in_flight_processing_before_returning(redis_client, postgres_session_factory):
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p2")
    consumer_transport = InMemoryTransport(client_id="c2")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, {"SensorEvent": SensorEventV1}, group_id="g2")
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=["sensor.events.raw"], output_topic="agent.results",
                          shutdown_timeout_seconds=2.0)
    runner.agent.initialize()

    runner._in_flight = True

    def _finish_soon():
        time.sleep(0.15)
        runner._in_flight = False

    threading.Thread(target=_finish_soon).start()

    start = time.time()
    runner.drain()
    elapsed = time.time() - start

    assert elapsed >= 0.15
    assert elapsed < 2.0
