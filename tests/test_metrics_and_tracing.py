"""
test_metrics_and_tracing.py

Proves metrics and tracing aren't just wired up cosmetically:
- Metrics: after running HelloAgent, the actual Prometheus counter/histogram
  values are inspected (not just "no exception was raised").
- Tracing: an in-memory OpenTelemetry span exporter captures real spans
  emitted during agent.process(), and we assert on their names and
  attributes (correlation_id propagation specifically).
"""
import datetime
import uuid

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry import trace as otel_trace
from prometheus_client import generate_latest

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


def test_metrics_reflect_real_processing_counts(redis_client, postgres_session_factory):
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    consumer_transport = InMemoryTransport(client_id="c")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, {"SensorEvent": SensorEventV1}, group_id="metrics-test-group")
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=["sensor.events.raw"], output_topic="agent.results")

    for _ in range(3):
        EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", _make_event())

    runner.run(max_iterations=3, max_empty_polls=50)

    metrics_output = generate_latest(agent.container.metrics.registry).decode()

    assert 'sentinel_HelloAgent_agent_process_total{outcome="success_with_result"} 3.0' in metrics_output
    assert "sentinel_HelloAgent_agent_process_duration_seconds_count" in metrics_output
    assert "sentinel_HelloAgent_agent_result_confidence" in metrics_output
    # every published result had confidence=1.0 -- the histogram's _sum should reflect that
    assert 'sentinel_HelloAgent_agent_result_confidence_sum 3.0' in metrics_output


def test_tracing_captures_real_spans_with_correlation_id_attributes(redis_client, postgres_session_factory):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)

    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p2")
    consumer_transport = InMemoryTransport(client_id="c2")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, {"SensorEvent": SensorEventV1}, group_id="trace-test-group")
    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = HelloAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=["sensor.events.raw"], output_topic="agent.results")

    event = _make_event()
    EventProducer(producer_transport, schema_provider).publish("sensor.events.raw", event)
    runner.run(max_iterations=1, max_empty_polls=20)

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    process_span = next(s for s in spans if s.name == "HelloAgent.process")
    attrs = dict(process_span.attributes)
    assert attrs["correlation_id"] == str(event.correlation_id)
    assert attrs["event_type"] == "SensorEventV1"
