"""
test_hello_agent_e2e.py

The formal version of the manual smoke test: publish a real SensorEvent,
run it through AgentRunner + HelloAgent, verify state was written to BOTH
real Redis and real Postgres, and a real AgentResult was published.
"""
import datetime
import uuid

from hello_agent import HelloAgent
from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.agent_result_v1 import AgentResultV1
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer, build_engine, build_session_factory
from sentinel_state.postgres_repositories import HelloSeenRepository


def _make_event(zone_id="Z-104", value=850.0):
    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(),
        producer_service="env-ingestion",
        producer_version="1.0.0",
        site_id="SITE-01",
        zone_id=zone_id,
        partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=SensorEventPayload(sensor_id="S-1", sensor_type=SensorType.GAS, value=value, unit="ppm", threshold_breached=True),
    )


def _build_runner(redis_client, postgres_session_factory):
    schema_provider = LocalSchemaProvider()
    # Separate transport instances per client -- exactly like real Kafka,
    # where each producer/consumer has its own connection. They share the
    # same underlying topic logs via InMemoryTransport's module-level
    # state, but closing one client's transport must NOT affect another's.
    producer_transport = InMemoryTransport(client_id="producer")
    consumer_transport = InMemoryTransport(client_id="hello-agent-consumer")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, {"SensorEvent": SensorEventV1}, group_id="hello-agent-group")
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=["sensor.events.raw"], output_topic="agent.results")
    return runner, producer_transport, schema_provider, state


def test_hello_agent_processes_event_and_writes_both_state_backends(redis_client, postgres_session_factory):
    runner, producer_transport, schema_provider, state = _build_runner(redis_client, postgres_session_factory)

    event = _make_event()
    EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", event)

    runner.run(max_iterations=1, max_empty_polls=20)

    assert runner._iterations_processed == 1
    assert state.hello.was_seen(str(event.event_id)) is True
    assert state.hello_pg.was_seen(str(event.event_id)) is True


def test_hello_agent_publishes_a_valid_agent_result(redis_client, postgres_session_factory):
    runner, producer_transport, schema_provider, state = _build_runner(redis_client, postgres_session_factory)

    event = _make_event()
    EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", event)
    runner.run(max_iterations=1, max_empty_polls=20)

    verify_transport = InMemoryTransport(client_id="verifier")
    result_consumer = EventConsumer(verify_transport, schema_provider, {"AgentResult": AgentResultV1}, group_id="verify-group")
    received = []
    result_consumer.subscribe(["agent.results"], handler=lambda e: received.append(e))
    outcome = result_consumer.poll_once()

    assert outcome is not None and outcome.status == "success"
    assert len(received) == 1
    result = received[0]
    assert result.payload.finding == "NO_FINDING"
    assert result.causation_id == event.event_id
    assert result.correlation_id == event.correlation_id
    assert len(result.explanation.evidence) > 0  # Domain Invariant #4


def test_hello_agent_readiness_reflects_real_backend_state(redis_client, postgres_session_factory):
    runner, producer_transport, schema_provider, state = _build_runner(redis_client, postgres_session_factory)
    event = _make_event()
    EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", event)
    runner.run(max_iterations=1, max_empty_polls=20)

    overall, checks = runner.health.readiness()
    from sentinel_agent_sdk.health import HealthStatus
    assert overall == HealthStatus.OK
    names = {c.name for c in checks}
    assert names == {"redis", "postgres"}  # only backends this agent's StateContainer actually has
