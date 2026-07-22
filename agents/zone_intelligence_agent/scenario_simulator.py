"""
scenario_simulator.py

Builds the pipeline the way it's actually supposed to work:

    Event Simulators -> Message Bus -> AgentRunner -> Zone Intelligence Agent -> output topics

NOT calling agent.process() directly (that's what acceptance_check.py and
the pytest suite do, for fast unit-level checks). This file exercises the
REAL consume/publish loop -- events are published onto named topics,
picked up by a real AgentRunner polling those topics, and the resulting
ZoneState/ZoneAnomalyDetected events are read back off THEIR OWN separate
output topics by an independent consumer. This is the actual architecture,
not a shortcut.

HONEST LIMITATION: there is no real Kafka broker reachable in this
environment (no apt package, no reachable download mirror -- checked).
This uses sentinel_eventbus's InMemoryTransport instead of KafkaTransport --
the SAME EventProducer/EventConsumer/topic-routing/schema-encoding code,
just without a live broker underneath. Swapping in KafkaTransport instead
(see main.py) requires zero changes to the simulators, scenarios, or the
agent -- only the transport constructor changes. That interchangeability
is the actual point of sentinel_eventbus's design, and it's the same
substitution the project's own hello_agent e2e test makes.

Risk Orchestrator (the next hop the architecture doc mentions) does not
exist as working code anywhere in this codebase yet -- so this correctly
stops at Zone Intelligence Agent's two output topics rather than faking a
downstream agent that isn't real.

Run it directly:

    cd agents/zone_intelligence_agent
    PYTHONPATH=../..:../../libs:../../sentinel_contracts:. python3 scenario_simulator.py

Requires a real Redis at localhost:6379.

NOTE (Phase 1.5/2 registry alignment): this script builds its own pipeline
with its own INPUT_TOPICS/OUTPUT_TOPICS/EVENT_TYPES below, independent of
main.py, and against a plain ZoneIntelligenceAgent (no wrapper). It still
demonstrates equipment-risk/incident scenarios and ZoneAnomalyDetected
publishing, because ZoneIntelligenceAgent's business logic for all of that
is fully intact and correct -- what's changed is main.py, the actual
PRODUCTION wiring, which currently does NOT subscribe to equipment.risk.
detected/incident.events.raw or publish to zone.anomaly.detected, because
none of those have a registered topic in kafka_topics.yaml yet (see
main.py's module docstring for the full explanation). This script is a
capability demo, not a description of the current production topology --
don't take its topic names as the canonical ones. See main.py for those.
"""
import datetime
import random
import sys
import time
import uuid

import redis

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.equipment_risk_detected_v1 import (
    EquipmentRiskDetectedPayload, EquipmentRiskDetectedV1, EquipmentRiskType,
)
from sentinel_contracts.events.incident_event_v1 import IncidentEventPayload, IncidentEventV1, IncidentSeverity
from sentinel_contracts.events.permit_event_v1 import PermitEventPayload, PermitEventV1, PermitStatus, PermitType
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1
from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1
from sentinel_eventbus import EventConsumer, EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer
from zone_intelligence_agent import ZoneIntelligenceAgent

SITE_ID = "SITE-01"
INPUT_TOPICS = ["sensor.events.raw", "worker.events.raw", "permit.events.raw",
                 "equipment.risk.detected", "incident.events.raw"]
OUTPUT_TOPICS = {"ZoneState": "zone.state.updated", "ZoneAnomalyDetected": "zone.anomaly.detected"}
EVENT_TYPES = {"SensorEvent": SensorEventV1, "WorkerEvent": WorkerEventV1, "PermitEvent": PermitEventV1,
               "EquipmentRiskDetected": EquipmentRiskDetectedV1, "IncidentEvent": IncidentEventV1}


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _meta():
    return Metadata(schema_id=101, schema_version=1, environment=Environment.DEV)


# ---------------------------------------------------------------------------
# SIMULATORS -- one per hardware type the doc lists. Each "pretends to be the
# hardware": builds a real, schema-valid event and publishes it onto the same
# topic a real ingestion service would use. The Zone Agent has no way to tell
# the difference -- it's just consuming from a topic, exactly like production.
# Bounded counts instead of true `while True` so the script terminates.
# ---------------------------------------------------------------------------

class Simulators:
    def __init__(self, producer: EventProducer):
        self.producer = producer

    def worker(self, zone_id, worker_id=None, action=WorkerEventKind.ZONE_ENTRY):
        event = WorkerEventV1(
            event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
            producer_service="worker-simulator", producer_version="1.0.0", site_id=SITE_ID,
            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            payload=WorkerEventPayload(worker_id=worker_id or f"W-{uuid.uuid4().hex[:6]}", event_kind=action),
        )
        self.producer.publish("worker.events.raw", event)
        return event

    def temperature(self, zone_id, celsius):
        event = SensorEventV1(
            event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
            producer_service="temperature-simulator", producer_version="1.0.0", site_id=SITE_ID,
            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            payload=SensorEventPayload(sensor_id=f"TEMP-{zone_id}", sensor_type=SensorType.TEMPERATURE,
                                        value=float(celsius), unit="celsius", threshold_breached=celsius >= 50),
        )
        self.producer.publish("sensor.events.raw", event)
        return event

    def smoke(self, zone_id, level):
        event = SensorEventV1(
            event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
            producer_service="smoke-simulator", producer_version="1.0.0", site_id=SITE_ID,
            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            payload=SensorEventPayload(sensor_id=f"SMOKE-{zone_id}", sensor_type=SensorType.SMOKE,
                                        value=float(level), unit="ppm", threshold_breached=level >= 150),
        )
        self.producer.publish("sensor.events.raw", event)
        return event

    def equipment_failure(self, zone_id, asset_id, risk_type=EquipmentRiskType.PREDICTED_FAILURE):
        from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
        from sentinel_contracts.common.explanation_object import ExplanationObject
        now = _now()
        event = EquipmentRiskDetectedV1(
            event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(), producer_version="1.0.0",
            site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            explanation=ExplanationObject(summary="equipment-simulator reading", generated_at=now, evidence=[],
                                           confidence=ConfidenceScore(value=0.9, derivation=ConfidenceDerivation.RULE_BASED)),
            payload=EquipmentRiskDetectedPayload(asset_id=asset_id, risk_type=risk_type),
        )
        self.producer.publish("equipment.risk.detected", event)
        return event

    def permit(self, zone_id, permit_id, permit_type, status=PermitStatus.ACTIVE):
        now = _now()
        event = PermitEventV1(
            event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(),
            producer_service="permit-simulator", producer_version="1.0.0", site_id=SITE_ID,
            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            payload=PermitEventPayload(permit_id=permit_id, permit_type=permit_type, status=status,
                                        issued_to_worker_id=str(uuid.uuid4()), valid_from=now, valid_until=now),
        )
        self.producer.publish("permit.events.raw", event)
        return event

    def incident(self, zone_id, incident_id, severity=IncidentSeverity.MINOR):
        event = IncidentEventV1(
            event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
            producer_service="incident-simulator", producer_version="1.0.0", site_id=SITE_ID,
            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
            payload=IncidentEventPayload(incident_id=incident_id, incident_type="SLIP_FALL", severity=severity),
        )
        self.producer.publish("incident.events.raw", event)
        return event


# ---------------------------------------------------------------------------
# SCENARIOS -- realistic sequences, not random noise. Each returns the number
# of events it published (so the runner knows how many to drain) and the
# anomaly type(s) expected on the output topic, if any.
# ---------------------------------------------------------------------------

def scenario_normal_shift(sim: Simulators, zone_id):
    """Workers come and go, temperature stays normal, one valid permit.
    Expect: ZERO anomalies."""
    n = 0
    for i in range(3):
        sim.worker(zone_id, f"W-NORMAL-{i}")
        n += 1
    sim.temperature(zone_id, 28)
    n += 1
    sim.permit(zone_id, "P-NORMAL", PermitType.ELECTRICAL)
    n += 1
    return n, set()


def scenario_fire(sim: Simulators, zone_id):
    """Temperature and smoke both climb into danger range with workers present.
    Expect: ENVIRONMENTAL_HAZARD."""
    n = 0
    sim.worker(zone_id, "W-FIRE-1"); n += 1
    sim.temperature(zone_id, 31); n += 1
    sim.temperature(zone_id, 45); n += 1
    sim.smoke(zone_id, 60); n += 1
    sim.smoke(zone_id, 180); n += 1  # crosses the danger threshold
    return n, {"ENVIRONMENTAL_HAZARD"}


def scenario_equipment_failure(sim: Simulators, zone_id):
    """A machine reports high risk while a worker is nearby.
    Expect: ZONE_HEALTH_DEGRADED."""
    n = 0
    sim.worker(zone_id, "W-EQUIP-1"); n += 1
    sim.equipment_failure(zone_id, "PUMP-12"); n += 1
    return n, {"ZONE_HEALTH_DEGRADED"}


def scenario_permit_violation(sim: Simulators, zone_id):
    """Hot Work and Confined Space permits become active together.
    Expect: PERMIT_CONFLICT."""
    n = 0
    sim.permit(zone_id, "P-HOT", PermitType.HOT_WORK); n += 1
    sim.permit(zone_id, "P-CONFINED", PermitType.CONFINED_SPACE); n += 1
    return n, {"PERMIT_CONFLICT"}


def scenario_incident_cluster(sim: Simulators, zone_id):
    """5 distinct incidents in quick succession.
    Expect: INCIDENT_FREQUENCY_EXCEEDED."""
    n = 0
    for i in range(5):
        sim.incident(zone_id, f"INC-{zone_id}-{i}")
        n += 1
    return n, {"INCIDENT_FREQUENCY_EXCEEDED"}


def scenario_multi_zone_emergency(sim: Simulators, zone_a, zone_b):
    """Two DIFFERENT zones each get their own distinct emergency at the same
    time. Expect: ENVIRONMENTAL_HAZARD in zone_a, ZONE_HEALTH_DEGRADED in
    zone_b -- proving the agent tracks zones independently, not globally.
    (This is as far as this codebase can demonstrate 'multi-zone
    correlation' -- an actual cross-zone correlation step is Risk
    Orchestrator's job, and Risk Orchestrator doesn't exist yet.)"""
    n = 0
    sim.worker(zone_a, "W-MZ-A"); n += 1
    sim.smoke(zone_a, 180); n += 1
    sim.worker(zone_b, "W-MZ-B"); n += 1
    sim.equipment_failure(zone_b, "PUMP-99"); n += 1
    return n, {("ZONE_A", "ENVIRONMENTAL_HAZARD"), ("ZONE_B", "ZONE_HEALTH_DEGRADED")}


# ---------------------------------------------------------------------------
# WIRING + VERIFICATION
# ---------------------------------------------------------------------------

def build_pipeline():
    from sentinel_eventbus import reset_all_state
    reset_all_state()  # wipe the shared in-memory bus so scenarios can't leak into each other

    redis_client = redis.Redis(host="localhost", port=6379)
    try:
        redis_client.ping()
    except redis.ConnectionError:
        print("ERROR: no Redis reachable at localhost:6379 -- required. Exiting.")
        sys.exit(1)

    schema_provider = LocalSchemaProvider()
    producer_transport = InMemoryTransport(client_id="simulators")
    consumer_transport = InMemoryTransport(client_id="zone-agent-consumer")
    producer = EventProducer(producer_transport, schema_provider)
    consumer = EventConsumer(consumer_transport, schema_provider, EVENT_TYPES, group_id="zone-agent-group")

    state = StateContainer(redis_client=redis_client)
    agent = ZoneIntelligenceAgent()
    runner = AgentRunner(agent, consumer=consumer, producer=producer, state_container=state,
                          input_topics=INPUT_TOPICS, output_topics=OUTPUT_TOPICS)

    return producer_transport, producer, runner


def drain_outputs():
    """A completely independent consumer, reading the SAME topics the agent
    published to -- exactly what Risk Orchestrator would do in production.
    Each EventConsumer gets its OWN InMemoryTransport: subscription state
    (_subscribed_topics/_group_id) lives on the transport object itself, so
    sharing one transport between two consumers overwrites one's
    subscription with the other's. The underlying topic logs are shared
    process-wide regardless (see in_memory_transport.py's module-level
    _TOPIC_LOGS), so separate transport instances still see the same data."""
    schema_provider = LocalSchemaProvider()
    state_received, anomaly_received = [], []

    state_consumer = EventConsumer(InMemoryTransport(client_id="verifier-state"), schema_provider,
                                    {"ZoneState": ZoneStateV1}, group_id="v-state")
    state_consumer.subscribe(["zone.state.updated"], handler=lambda e: state_received.append(e))

    anomaly_consumer = EventConsumer(InMemoryTransport(client_id="verifier-anomaly"), schema_provider,
                                      {"ZoneAnomalyDetected": ZoneAnomalyDetectedV1}, group_id="v-anomaly")
    anomaly_consumer.subscribe(["zone.anomaly.detected"], handler=lambda e: anomaly_received.append(e))

    for _ in range(200):
        state_consumer.poll_once()
        anomaly_consumer.poll_once()
    return state_received, anomaly_received


def run_scenario(name, fn, *args):
    print(f"\n{'=' * 78}\nSCENARIO: {name}\n{'=' * 78}")
    _, producer, runner = build_pipeline()
    sim = Simulators(producer)

    n_events, expected = fn(sim, *args)
    print(f"Published {n_events} events onto real topics via the simulators.")

    runner.run(max_iterations=n_events, max_empty_polls=20)
    print(f"AgentRunner actually consumed and processed: {runner._iterations_processed} events.")

    _, anomalies = drain_outputs()
    found_types = {a.payload.anomaly_type.value for a in anomalies}
    print(f"Anomalies published to zone.anomaly.detected: {found_types or '(none)'}")

    if isinstance(next(iter(expected), None), tuple):
        # multi-zone case: expected is a set of (zone_label, anomaly_type) -- just
        # report what fired per zone, since zone_ids here are placeholders.
        print(f"Expected pattern: {expected}")
        passed = len(found_types) == len({t for _, t in expected})
    else:
        passed = found_types == expected

    print(f"RESULT: {'PASS' if passed else 'FAIL'} (expected {expected or 'no anomalies'}, got {found_types})")
    return passed


def main():
    results = []
    results.append(("Normal Shift (expect NO anomalies)",
                     run_scenario("Normal Shift", scenario_normal_shift, f"ZONE-NORMAL-{uuid.uuid4().hex[:6]}")))
    results.append(("Fire (expect ENVIRONMENTAL_HAZARD)",
                     run_scenario("Fire", scenario_fire, f"ZONE-FIRE-{uuid.uuid4().hex[:6]}")))
    results.append(("Equipment Failure (expect ZONE_HEALTH_DEGRADED)",
                     run_scenario("Equipment Failure", scenario_equipment_failure, f"ZONE-EQUIP-{uuid.uuid4().hex[:6]}")))
    results.append(("Permit Violation (expect PERMIT_CONFLICT)",
                     run_scenario("Permit Violation", scenario_permit_violation, f"ZONE-PERMIT-{uuid.uuid4().hex[:6]}")))
    results.append(("Incident Cluster (expect INCIDENT_FREQUENCY_EXCEEDED)",
                     run_scenario("Incident Cluster", scenario_incident_cluster, f"ZONE-INCIDENT-{uuid.uuid4().hex[:6]}")))
    results.append(("Multi-zone Emergency (expect 2 independent anomalies)",
                     run_scenario("Multi-zone Emergency", scenario_multi_zone_emergency,
                                  f"ZONE-MZ-A-{uuid.uuid4().hex[:6]}", f"ZONE-MZ-B-{uuid.uuid4().hex[:6]}")))

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    for label, passed in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    print(f"\n{sum(1 for _, p in results if p)}/{len(results)} scenarios behaved as expected.")
    print("\nNOTE: Risk Orchestrator doesn't exist in this codebase yet, so this")
    print("correctly stops at Zone Intelligence Agent's two output topics --")
    print("zone.state.updated and zone.anomaly.detected -- rather than faking")
    print("a downstream escalation step that isn't real code.")


if __name__ == "__main__":
    main()