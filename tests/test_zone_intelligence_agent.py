"""
test_zone_intelligence_agent_e2e.py

Runs ZoneIntelligenceAgent through the full AgentRunner loop (not just
direct process() calls) to prove the new multi-event-type output routing
(one input event producing BOTH a ZoneState and a ZoneAnomalyDetected,
published to two different topics) works end-to-end.

NOTE (Phase 1.5/2 registry alignment): this test builds its OWN AgentRunner
with a plain ZoneIntelligenceAgent and its own local topic strings -- it
does NOT import from main.py. sentinel.sensor.events.v1 and
sentinel.zone.state.v1 below are the actual registered topic names (see
main.py). "zone.anomaly.detected" is NOT a registered topic (no entry
exists in kafka_topics.yaml for ZoneAnomalyDetected) -- it's a local,
test-only topic name that exercises the SDK's multi-output-topic routing
capability at the agent/SDK level. In the real deployment (main.py),
publishing ZoneAnomalyDetected is currently suppressed at the wiring layer
(see main.py's _ZoneAnomalySuppressingAgent) because that topic isn't
registered; this test is unaffected by that since it never goes through
main.py.
"""
import datetime
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents" / "zone_intelligence_agent"))

from zone_intelligence_agent import ZoneIntelligenceAgent

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer


def test_zone_intelligence_agent_publishes_to_two_different_topics(redis_client):
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    consumer_transport = InMemoryTransport(client_id="c")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(
        consumer_transport, schema_provider,
        {"SensorEvent": SensorEventV1}, group_id="zone-intel-group",
    )
    state = StateContainer(redis_client=redis_client)
    agent = ZoneIntelligenceAgent()

    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=["sentinel.sensor.events.v1"],
        output_topics={"ZoneState": "sentinel.zone.state.v1", "ZoneAnomalyDetected": "zone.anomaly.detected"},
    )

    event = SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(), producer_service="env-ingestion", producer_version="1.0.0",
        site_id="SITE-01", zone_id="Z-104", partition_key="Z-104",
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=SensorEventPayload(sensor_id="S-1", sensor_type=SensorType.GAS, value=900.0,
                                    unit="ppm", threshold_breached=True),
    )
    EventProducer(producer_transport, schema_provider).publish("sentinel.sensor.events.v1", event)

    runner.run(max_iterations=1, max_empty_polls=20)

    # verify BOTH topics received the correct event type
    verify_transport_a = InMemoryTransport(client_id="verify-a")
    zone_state_consumer = EventConsumer(verify_transport_a, schema_provider, {"ZoneState": ZoneStateV1}, group_id="verify-a")
    zone_state_received = []
    zone_state_consumer.subscribe(["sentinel.zone.state.v1"], handler=lambda e: zone_state_received.append(e))
    outcome_a = zone_state_consumer.poll_once()

    verify_transport_b = InMemoryTransport(client_id="verify-b")
    anomaly_consumer = EventConsumer(verify_transport_b, schema_provider, {"ZoneAnomalyDetected": ZoneAnomalyDetectedV1}, group_id="verify-b")
    anomaly_received = []
    anomaly_consumer.subscribe(["zone.anomaly.detected"], handler=lambda e: anomaly_received.append(e))
    outcome_b = anomaly_consumer.poll_once()

    assert outcome_a.status == "success"
    assert outcome_b.status == "success"
    assert len(zone_state_received) == 1
    assert len(anomaly_received) == 1
    assert zone_state_received[0].payload.active_sensor_alert_ids == ["S-1"]
    assert anomaly_received[0].payload.anomaly_type.value == "ENVIRONMENTAL_HAZARD"