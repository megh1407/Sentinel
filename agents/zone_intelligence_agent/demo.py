"""
demo.py

Standalone, runnable walkthrough of Zone Intelligence Agent -- NOT a pytest
file. Run it directly and watch real output:

    cd agents/zone_intelligence_agent
    PYTHONPATH=../..:../../libs:../../sentinel_contracts:. python3 demo.py

Requires a real Redis reachable at localhost:6379 (required). Postgres at
localhost:5432 (user postgres / password localdev / db "sentinel") is
OPTIONAL -- if it's not reachable, the demo prints a warning and continues
with Redis-only behavior, exactly like the agent itself degrades.

Each scenario below: builds a real event -> feeds it to the real agent ->
prints exactly what came back (ZoneState and/or ZoneAnomalyDetected) with
its full explanation, so you can see the actual decision, not just a
pass/fail dot.
"""
import datetime
import os
import sys
import uuid

import redis

from sentinel_agent_sdk.container import build_container
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.equipment_risk_detected_v1 import (
    EquipmentRiskDetectedPayload, EquipmentRiskDetectedV1, EquipmentRiskType,
)
from sentinel_contracts.events.incident_event_v1 import IncidentEventPayload, IncidentEventV1, IncidentSeverity
from sentinel_contracts.events.permit_event_v1 import PermitEventPayload, PermitEventV1, PermitStatus, PermitType
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorType
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1
from sentinel_eventbus import EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer, build_engine, build_session_factory
from zone_intelligence_agent import ZoneIntelligenceAgent

SITE_ID = "SITE-01"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def worker_event(zone_id, worker_id, kind=WorkerEventKind.ZONE_ENTRY):
    return WorkerEventV1(
        event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
        producer_service="worker-tracking", producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind),
    )


def sensor_event(zone_id, sensor_id, value, breached):
    return SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
        producer_service="env-ingestion", producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=SensorEventPayload(sensor_id=sensor_id, sensor_type=SensorType.GAS, value=value,
                                    unit="ppm", threshold_breached=breached),
    )


def permit_event(zone_id, permit_id, permit_type, status=PermitStatus.ACTIVE):
    now = _now()
    return PermitEventV1(
        event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(),
        producer_service="permit-system", producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=PermitEventPayload(permit_id=permit_id, permit_type=permit_type, status=status,
                                    issued_to_worker_id=str(uuid.uuid4()), valid_from=now, valid_until=now),
    )


def equipment_risk_event(zone_id, asset_id, risk_type=EquipmentRiskType.ABNORMAL_TEMPERATURE):
    now = _now()
    return EquipmentRiskDetectedV1(
        event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(), producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        explanation=_stub_explanation(),
        payload=EquipmentRiskDetectedPayload(asset_id=asset_id, risk_type=risk_type),
    )


def incident_event(zone_id, incident_id, severity=IncidentSeverity.MINOR):
    return IncidentEventV1(
        event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
        producer_service="incident-system", producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id,
        metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
        payload=IncidentEventPayload(incident_id=incident_id, incident_type="SLIP_FALL", severity=severity),
    )


def _stub_explanation():
    from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
    from sentinel_contracts.common.explanation_object import ExplanationObject
    now = _now()
    return ExplanationObject(summary="upstream producer's explanation (not this agent's)", generated_at=now,
                              evidence=[], confidence=ConfidenceScore(value=0.9, derivation=ConfidenceDerivation.RULE_BASED))


def show(label, results):
    print(f"\n>>> {label}")
    if not results:
        print("    (dropped -- e.g. no zone_id to correlate against, see agent's known gaps)")
        return
    for item in results:
        kind = type(item).__name__
        if kind == "ZoneStateV1":
            p = item.payload
            print(f"    ZoneState: occupancy={p.occupancy_count} risk={p.current_risk_level.value} "
                  f"sensors_alerting={p.active_sensor_alert_ids} permits={p.active_permit_ids} "
                  f"equipment_risks={p.active_equipment_risk_ids} recent_incidents={p.recent_incident_count}")
        else:
            p = item.payload
            print(f"    *** ANOMALY: {p.anomaly_type.value} (severity={p.severity.value}) ***")
            print(f"        summary: {item.explanation.summary}")
            print(f"        confidence: {item.explanation.confidence.value} (rule: {item.explanation.confidence.rule_id})")


def build_agent():
    redis_client = redis.Redis(host="localhost", port=6379)
    try:
        redis_client.ping()
    except redis.ConnectionError:
        print("ERROR: no Redis reachable at localhost:6379 -- this demo requires it. Exiting.")
        sys.exit(1)

    postgres_session_factory = None
    try:
        from sentinel_state.postgres_repositories import ZoneRepository
        # Phase 3 remediation note (SENTINEL forensic audit, security
        # baseline): was a hardcoded DSN with a literal password. Same
        # local-dev default, now overridable via env var.
        dsn = os.environ.get(
            "SENTINEL_DEMO_POSTGRES_DSN",
            "postgresql+psycopg2://postgres:localdev@localhost:5432/sentinel",
        )
        engine = build_engine(dsn)
        postgres_session_factory = build_session_factory(engine)
        ZoneRepository(postgres_session_factory).ensure_schema()
        print("Postgres: connected -- zone_history/anomalies/audit_events will be written for real.")
    except Exception as e:
        print(f"Postgres: not available ({e}) -- continuing Redis-only, same as the agent does in production "
              f"when Postgres isn't configured.")

    state = StateContainer(redis_client=redis_client, postgres_session_factory=postgres_session_factory)
    agent = ZoneIntelligenceAgent()
    producer = EventProducer(InMemoryTransport(client_id="demo"), LocalSchemaProvider())
    agent.container = build_container("ZoneIntelligenceAgent", state, producer)
    agent.initialize()
    return agent


def main():
    agent = build_agent()
    zone = f"Z-DEMO-{uuid.uuid4().hex[:6]}"
    print(f"\nUsing a fresh zone_id for this run: {zone}\n" + "=" * 70)

    show("Rule 2 -- dangerous sensor reading (gas breach)",
         agent.process(sensor_event(zone, "GAS-1", value=910.0, breached=True)))

    show("Rule 1 -- worker enters (1st of many, no anomaly yet)",
         agent.process(worker_event(zone, "W-1")))

    for i in range(2, 12):
        results = agent.process(worker_event(zone, f"W-{i}"))
    show("Rule 1 -- occupancy exceeded (11th worker just entered)", results)

    show("Rule 5 -- equipment risk arrives in an already-occupied zone",
         agent.process(equipment_risk_event(zone, "EQ-1")))

    show("Rule 3 -- Hot Work permit goes active",
         agent.process(permit_event(zone, "P-HOT", PermitType.HOT_WORK)))
    show("Rule 3 -- Confined Space permit ALSO goes active -> conflict",
         agent.process(permit_event(zone, "P-CONFINED", PermitType.CONFINED_SPACE)))

    for i in range(4):
        results = agent.process(incident_event(zone, f"INC-{i}"))
    show("Rule 4 -- incident frequency exceeded (4th distinct incident)", results)

    print("\n" + "=" * 70)
    print("Done. Every ZoneState/anomaly shown above is a REAL object the agent")
    print("produced and (if Postgres was connected) really wrote to Postgres --")
    print("check zone_intelligence.zone_history / .anomalies for zone_id:", zone)


if __name__ == "__main__":
    main()
