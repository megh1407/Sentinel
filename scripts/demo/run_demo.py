"""
scripts/demo/run_demo.py -- Phase 11 demo generator

Publishes ONE reproducible scenario -- the exact T0-T5 sequence from the
master integration prompt -- as real, contract-valid events onto the real
Kafka(-equivalent) topics the four agents actually subscribe to:

    T0: Zone A - normal (baseline sensor + worker + permit context)
    T1: Temperature rises
    T2: Three distinct gas species report (methane, carbon monoxide,
                                   hydrogen sulfide -- see the B3 note
                                   below: this now DOES independently move
                                   risk_score per species, since B3 is
                                   resolved)
    T3: Hot-work permit becomes active
    T4: Workers enter the zone with a PPE violation
    T5: Zone risk increases (driven by the accumulated sensor/worker signals)

This script does NOT invent a compound-risk decision -- per the master
prompt's Phase 11 instruction, that's the future Risk Orchestrator's job.
It only publishes independent signals and lets the four real agents react
to them independently, exactly as they do in production.

B3 (gas-species disambiguation) IS NOW RESOLVED: SensorType still has a
single undifferentiated GAS value, but SensorEventPayload's existing
`raw_metadata: dict[str, str]` extensibility field now carries a
`gas_species` tag (see `_gas_event()` below) -- no schema change, since
that field was already part of the canonical contract. The Environmental
Agent's SensorSnapshotAggregator folds recognized species (methane,
carbon_monoxide, hydrogen_sulfide, oxygen, voc, ammonia) into its snapshot
by name, and ThresholdService already had real, configured thresholds for
all six -- so each species below DOES independently move risk_score and
appear as a real, correctly-classified hazard (flammable_gas /
toxic_gas / oxygen_deficiency) in the resulting EnvironmentAnalysis. An
untagged or unrecognized-species GAS reading is still honestly dropped,
not guessed at.

Usage:
    Run this in the SAME process as platform-services/api-gateway/main.py
    (import and call run_demo(producer) after startup), OR run standalone
    against the same InMemoryTransport process-wide state if imported
    before the module is torn down. Because InMemoryTransport's topic log
    is process-wide (see libs/sentinel_eventbus/in_memory_transport.py),
    running this as a *separate* `python run_demo.py` process will NOT be
    seen by an API-gateway process started separately -- there is no
    shared broker in this environment. See README in this directory.
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs"))
sys.path.insert(0, str(REPO_ROOT))

from sentinel_eventbus import EventProducer, InMemoryTransport, LocalSchemaProvider  # noqa: E402
from sentinel_contracts.common.metadata import Metadata, Environment  # noqa: E402
from sentinel_contracts.events.sensor_event_v1 import (  # noqa: E402
    SensorEventV1, SensorEventPayload, SensorType, SensorStatus,
)
from sentinel_contracts.events.worker_event_v1 import (  # noqa: E402
    WorkerEventV1, WorkerEventPayload, WorkerEventKind,
)
from sentinel_contracts.events.permit_event_v1 import (  # noqa: E402
    PermitEventV1, PermitEventPayload, PermitType, PermitStatus,
)

SITE_ID = "SITE-1"
ZONE_ID = "ZONE-A"


def _meta() -> Metadata:
    return Metadata(schema_id=1, schema_version=1, environment=Environment.DEV)


def _sensor_event(sensor_type: SensorType, value: float, unit: str, sensor_id: str) -> SensorEventV1:
    return SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=ZONE_ID, partition_key=ZONE_ID, trace_id=None,
        metadata=_meta(),
        payload=SensorEventPayload(
            sensor_id=sensor_id, sensor_type=sensor_type, value=value, unit=unit,
            threshold_breached=False, sensor_status=SensorStatus.ACTIVE,
        ),
    )


def _gas_event(species: str, value: float, unit: str, sensor_id: str) -> SensorEventV1:
    """B3 RESOLVED (see the environmental agent's audit / sensor_snapshot_
    aggregator.py) -- gas species now rides in payload.raw_metadata, the
    contract's existing extensibility field. No SensorEventPayload schema
    change was needed."""
    return SensorEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=ZONE_ID, partition_key=ZONE_ID, trace_id=None,
        metadata=_meta(),
        payload=SensorEventPayload(
            sensor_id=sensor_id, sensor_type=SensorType.GAS, value=value, unit=unit,
            threshold_breached=False, sensor_status=SensorStatus.ACTIVE,
            raw_metadata={"gas_species": species},
        ),
    )


def _worker_event(worker_id: str, kind: WorkerEventKind, ppe_status: dict[str, bool] | None) -> WorkerEventV1:
    return WorkerEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=ZONE_ID, partition_key=ZONE_ID, trace_id=None,
        metadata=_meta(),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind, ppe_status=ppe_status),
    )


def _permit_event(permit_id: str, permit_type: PermitType, status: PermitStatus, worker_id: str) -> PermitEventV1:
    now = datetime.now(timezone.utc)
    return PermitEventV1(
        event_id=uuid.uuid4(), event_timestamp=now,
        correlation_id=uuid.uuid4(), causation_id=None,
        producer_service="demo-generator", producer_version="1.0",
        site_id=SITE_ID, zone_id=ZONE_ID, partition_key=ZONE_ID, trace_id=None,
        metadata=_meta(),
        payload=PermitEventPayload(
            permit_id=permit_id, permit_type=permit_type, status=status,
            issued_to_worker_id=worker_id, valid_from=now, valid_until=now + timedelta(hours=4),
        ),
    )


def run_demo(producer: EventProducer, tick_seconds: float = 2.0) -> None:
    print(f"[demo] Zone {ZONE_ID} -- T0: normal baseline")
    producer.publish("sentinel.sensor.events.v1", _sensor_event(SensorType.TEMPERATURE, 24.0, "C", "TEMP-A1"))
    for i in range(1, 19):
        producer.publish("sentinel.worker.events.v1", _worker_event(
            f"W-{i:03d}", WorkerEventKind.ZONE_ENTRY, {"helmet": True, "vest": True, "gloves": True},
        ))
    time.sleep(tick_seconds)

    print("[demo] T1: temperature rises")
    producer.publish("sentinel.sensor.events.v1", _sensor_event(SensorType.TEMPERATURE, 48.0, "C", "TEMP-A1"))
    time.sleep(tick_seconds)

    print("[demo] T2: gas sensors report -- three real, distinct species (B3 resolved, see run_demo.py's _gas_event)")
    producer.publish("sentinel.sensor.events.v1", _gas_event("methane", 900.0, "ppm", "GAS-A1-CH4"))
    producer.publish("sentinel.sensor.events.v1", _gas_event("carbon_monoxide", 40.0, "ppm", "GAS-A1-CO"))
    producer.publish("sentinel.sensor.events.v1", _gas_event("hydrogen_sulfide", 3.0, "ppm", "GAS-A1-H2S"))
    time.sleep(tick_seconds)

    print("[demo] T3: hot-work permit becomes active")
    producer.publish("sentinel.permit.events.v1", _permit_event(
        "PERMIT-501", PermitType.HOT_WORK, PermitStatus.ACTIVE, "W-001",
    ))
    time.sleep(tick_seconds)

    print("[demo] T4: workers enter zone with a PPE violation")
    producer.publish("sentinel.worker.events.v1", _worker_event(
        "W-019", WorkerEventKind.ZONE_ENTRY, {"helmet": False, "vest": True, "gloves": False},
    ))
    producer.publish("sentinel.worker.events.v1", _worker_event(
        "W-001", WorkerEventKind.PPE_STATUS, {"helmet": True, "vest": False, "gloves": True},
    ))
    time.sleep(tick_seconds)

    print("[demo] T5: further temperature rise -- zone risk accumulates from independent signals")
    producer.publish("sentinel.sensor.events.v1", _sensor_event(SensorType.TEMPERATURE, 61.0, "C", "TEMP-A1"))
    print("[demo] scenario complete -- no compound-risk decision was made; that is the future Risk Orchestrator's job")


if __name__ == "__main__":
    schema_provider = LocalSchemaProvider()
    producer = EventProducer(InMemoryTransport(client_id="demo-generator"), schema_provider)
    print(
        "[demo] WARNING: this InMemoryTransport instance is only visible to agents\n"
        "        started in THIS process. Import run_demo() from the api-gateway\n"
        "        startup instead of running this file standalone if you want the\n"
        "        API/dashboard to see these events. See this file's module docstring."
    )
    run_demo(producer)
