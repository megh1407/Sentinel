"""demo_scenarios.py -- deterministic demo scenarios (master prompt Phase 9).

Each scenario injects REAL, contract-valid events into the REAL pipeline via
the same InMemoryTransport producer the four agents consume from. It does NOT
touch frontend state, does NOT fabricate risk -- the risk that appears is
whatever the real agents + Risk Orchestrator compute from these events.

Scenarios:
  normal               -- baseline sensor values, compliant workers -> LOW/monitoring
  gas-rise             -- methane ramps 300->1200->3000->7000 ppm -> risk climbs
  compound-risk        -- gas rise + PPE violation + active hot-work permit
  multi-zone-emergency -- critical gas + worker exposure in ZONE-A, presence in
                          ZONE-B/C/D (the Neo4j-connected neighbours) so
                          propagation/affected-zones light up

Reuses the event builders' shapes from scripts/demo/run_demo.py, generalized
to take a zone_id so multi-zone works.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.sensor_event_v1 import (
    SensorEventV1, SensorEventPayload, SensorType, SensorStatus,
)
from sentinel_contracts.events.worker_event_v1 import (
    WorkerEventV1, WorkerEventPayload, WorkerEventKind,
)
from sentinel_contracts.events.permit_event_v1 import (
    PermitEventV1, PermitEventPayload, PermitType, PermitStatus,
)

SITE_ID = "SITE-1"
SENSOR_TOPIC = "sentinel.sensor.events.v1"
WORKER_TOPIC = "sentinel.worker.events.v1"
PERMIT_TOPIC = "sentinel.permit.events.v1"


def _meta() -> Metadata:
    return Metadata(schema_id=1, schema_version=1, environment=Environment.DEV)


def _sensor(zone, sensor_type, value, unit, sensor_id):
    return SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=zone, partition_key=zone, trace_id=None, metadata=_meta(),
        payload=SensorEventPayload(sensor_id=sensor_id, sensor_type=sensor_type, value=value,
            unit=unit, threshold_breached=False, sensor_status=SensorStatus.ACTIVE),
    )


def _gas(zone, species, value, sensor_id):
    return SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=zone, partition_key=zone, trace_id=None, metadata=_meta(),
        payload=SensorEventPayload(sensor_id=sensor_id, sensor_type=SensorType.GAS, value=value,
            unit="ppm", threshold_breached=False, sensor_status=SensorStatus.ACTIVE,
            raw_metadata={"gas_species": species}),
    )


def _worker(zone, worker_id, kind, ppe):
    return WorkerEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=zone, partition_key=zone, trace_id=None, metadata=_meta(),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind, ppe_status=ppe),
    )


def _permit(zone, permit_id, worker_id):
    now = datetime.now(timezone.utc)
    return PermitEventV1(
        event_id=uuid.uuid4(), event_timestamp=now,
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=zone, partition_key=zone, trace_id=None, metadata=_meta(),
        payload=PermitEventPayload(permit_id=permit_id, permit_type=PermitType.HOT_WORK,
            status=PermitStatus.ACTIVE, issued_to_worker_id=worker_id,
            valid_from=now, valid_until=now + timedelta(hours=4)),
    )


# -- scenarios -------------------------------------------------------------

def scenario_normal(producer, tick=1.0):
    for i in range(1, 6):
        producer.publish(WORKER_TOPIC, _worker("ZONE-A", f"W-{i:03d}", WorkerEventKind.ZONE_ENTRY,
                                               {"helmet": True, "vest": True, "gloves": True}))
    producer.publish(SENSOR_TOPIC, _sensor("ZONE-A", SensorType.TEMPERATURE, 22.0, "C", "TEMP-A1"))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "methane", 120.0, "GAS-A1-CH4"))
    time.sleep(tick)


def scenario_gas_rise(producer, tick=2.0):
    """Methane climbs through advisory -> warning -> high -> critical."""
    producer.publish(SENSOR_TOPIC, _sensor("ZONE-A", SensorType.TEMPERATURE, 24.0, "C", "TEMP-A1"))
    for value in (300.0, 1200.0, 3000.0, 7000.0):
        producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "methane", value, "GAS-A1-CH4"))
        time.sleep(tick)


def scenario_compound_risk(producer, tick=2.0):
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "methane", 1500.0, "GAS-A1-CH4"))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "carbon_monoxide", 60.0, "GAS-A1-CO"))
    time.sleep(tick)
    producer.publish(PERMIT_TOPIC, _permit("ZONE-A", "PERMIT-501", "W-001"))
    time.sleep(tick)
    producer.publish(WORKER_TOPIC, _worker("ZONE-A", "W-019", WorkerEventKind.PPE_STATUS,
                                           {"helmet": False, "vest": True, "gloves": False}))
    producer.publish(SENSOR_TOPIC, _sensor("ZONE-A", SensorType.TEMPERATURE, 58.0, "C", "TEMP-A1"))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "methane", 4000.0, "GAS-A1-CH4"))
    time.sleep(tick)


def scenario_multi_zone_emergency(producer, tick=2.0):
    # ZONE-A: critical gas + worker exposure + PPE violation + hot-work permit
    producer.publish(PERMIT_TOPIC, _permit("ZONE-A", "PERMIT-777", "W-001"))
    producer.publish(WORKER_TOPIC, _worker("ZONE-A", "W-050", WorkerEventKind.PPE_STATUS,
                                           {"helmet": False, "vest": False, "gloves": True}))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "methane", 8000.0, "GAS-A1-CH4"))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-A", "carbon_monoxide", 200.0, "GAS-A1-CO"))
    producer.publish(SENSOR_TOPIC, _sensor("ZONE-A", SensorType.TEMPERATURE, 65.0, "C", "TEMP-A1"))
    time.sleep(tick)
    # Neighbour zones (topology): workers present in adjacent ZONE-C, presence
    # via shared-ventilation ZONE-B, evacuation route ZONE-D.
    producer.publish(WORKER_TOPIC, _worker("ZONE-C", "W-060", WorkerEventKind.ZONE_ENTRY,
                                           {"helmet": True, "vest": True, "gloves": True}))
    producer.publish(SENSOR_TOPIC, _gas("ZONE-B", "methane", 1200.0, "GAS-B1-CH4"))
    producer.publish(WORKER_TOPIC, _worker("ZONE-D", "W-070", WorkerEventKind.ZONE_ENTRY,
                                           {"helmet": True, "vest": True, "gloves": True}))
    time.sleep(tick)


SCENARIOS = {
    "normal": scenario_normal,
    "gas-rise": scenario_gas_rise,
    "compound-risk": scenario_compound_risk,
    "multi-zone-emergency": scenario_multi_zone_emergency,
}
