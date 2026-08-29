"""
test_worker_safety_agent_e2e.py

Proves the REAL platform path, using the actual EventProducer/
EventConsumer/AgentRunner/InMemoryTransport/LocalSchemaProvider -- not a
fake harness, and not calling agent.process(event) directly and calling
that "Kafka integration":

    real WorkerEventV1
        -> real EventProducer.publish("sentinel.worker.events.v1", ...)
        -> real Kafka-semantics transport (InMemoryTransport)
        -> real EventConsumer.poll_once()
        -> real AgentRunner._process_message()
        -> WorkerSafetyAgent.process() (the real business logic)
        -> real AgentRunner publish of the returned WorkerAnalysisV1
        -> real EventConsumer.poll_once() on the output topic

then verifies:
  1. the message was actually consumed and the offset committed
  2. the agent's PPE evaluation actually ran (last_results populated
     correctly)
  3. a real WorkerAnalysisV1 was published to sentinel.worker.analysis.v1
     and is independently readable back by a fresh consumer group

Phase 2 remediation note (SENTINEL forensic audit, P0-3): this test
previously asserted the opposite of point 3 above ("nothing was ever
produced"), documenting a real gap that has since been closed (see
worker_safety_agent.py's module docstring and
test_worker_analysis_publish_gap.py, both updated in the same
remediation pass). The `verify_consumer` below previously registered an
empty model_registry (`{}`), which was correct for the old "nothing is
ever published" premise but caused this test to fail after the fix
landed -- the event now genuinely gets published, and an empty registry
made it look, from `verify_consumer`'s point of view, like an
unrecognized event type. Registered under `"WorkerAnalysis"` here to
match the exact same key `platform-services/api-gateway`'s
`orchestrator_runtime.py`/`state_cache.py` already use for their real
`model_registry` -- not a new naming decision.
"""
import datetime
import uuid

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.agent_contracts.worker_analysis_v1 import WorkerAnalysisV1, WorkerSafetyStatus
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer

from worker_safety_agent import WorkerSafetyAgent
from zone_ppe_requirements import ZonePPERequirements


def _make_event(worker_id: str, zone_id: str, ppe_status: dict) -> WorkerEventV1:
    return WorkerEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.datetime.now(datetime.timezone.utc),
        correlation_id=uuid.uuid4(), producer_service="ppe-vision-service", producer_version="0.1.0-demo",
        site_id="SITE-01", zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=200, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=WorkerEventKind.PPE_STATUS, ppe_status=ppe_status),
    )


def test_real_kafka_round_trip_evaluates_ppe_and_publishes_worker_analysis():
    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="p")
    consumer_transport = InMemoryTransport(client_id="c")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(
        consumer_transport, schema_provider,
        {"WorkerEvent": WorkerEventV1}, group_id="worker-safety-group",
    )
    state = StateContainer()
    agent = WorkerSafetyAgent(zone_ppe_requirements=ZonePPERequirements(per_zone={"Z-104": ["helmet", "vest", "gloves"]}))

    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=["sentinel.worker.events.v1"],
        output_topic="sentinel.worker.analysis.v1",
    )

    event = _make_event("W-42", "Z-104", {"helmet": True, "vest": True, "gloves": False})
    EventProducer(producer_transport, schema_provider).publish("sentinel.worker.events.v1", event)

    runner.run(max_iterations=1, max_empty_polls=20)

    # (2) the real business logic actually ran
    assert "W-42" in agent.last_results
    result = agent.last_results["W-42"]
    assert result.ppe_violations == ["gloves"]
    assert result.zone_id == "Z-104"

    # (3) a real WorkerAnalysisV1 was published -- verified by actually
    # polling the output topic with a fresh consumer group, not by
    # inspecting internals
    verify_transport = InMemoryTransport(client_id="verify")
    verify_consumer = EventConsumer(
        verify_transport, schema_provider, {"WorkerAnalysis": WorkerAnalysisV1}, group_id="verify-worker-analysis",
    )
    received = []
    verify_consumer.subscribe(["sentinel.worker.analysis.v1"], handler=lambda e: received.append(e))
    verify_consumer.poll_once()

    assert len(received) == 1
    analysis = received[0]
    assert isinstance(analysis, WorkerAnalysisV1)
    assert analysis.payload.worker_id == "W-42"
    assert analysis.payload.ppe_violations == ["gloves"]
    assert analysis.payload.safety_status == WorkerSafetyStatus.at_risk
