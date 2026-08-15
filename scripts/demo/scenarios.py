"""scenarios.py — Deterministic Demo Scenario System for SENTINEL.

Injects real, contract-valid events onto Kafka/InMemory topics for:
  - Scenario 1: NORMAL
  - Scenario 2: GAS-RISE (Single-Zone Gas Hazard)
  - Scenario 3: COMPOUND-RISK (Gas + PPE Violation + Hot Work Permit)
  - Scenario 4: MULTI-ZONE-EMERGENCY (Critical leak + Ventilation/Route propagation)
  - RESET: Clears live demo state & idempotency caches.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.permit_event_v1 import PermitEventPayload, PermitEventV1, PermitStatus, PermitType
from sentinel_contracts.events.sensor_event_v1 import SensorEventPayload, SensorEventV1, SensorStatus, SensorType
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventPayload, WorkerEventV1

logger = logging.getLogger(__name__)

SITE_ID = "SITE-1"


def _meta() -> Metadata:
    return Metadata(schema_id=1, schema_version=1, environment=Environment.DEV)


def _sensor_event(zone_id: str, sensor_type: SensorType, value: float, unit: str, sensor_id: str) -> SensorEventV1:
    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(),
        causation_id=None,
        producer_service="demo-generator",
        producer_version="1.0",
        site_id=SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=None,
        metadata=_meta(),
        payload=SensorEventPayload(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            threshold_breached=False,
            sensor_status=SensorStatus.ACTIVE,
        ),
    )


def _gas_event(zone_id: str, species: str, value: float, unit: str, sensor_id: str) -> SensorEventV1:
    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(),
        causation_id=None,
        producer_service="demo-generator",
        producer_version="1.0",
        site_id=SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=None,
        metadata=_meta(),
        payload=SensorEventPayload(
            sensor_id=sensor_id,
            sensor_type=SensorType.GAS,
            value=value,
            unit=unit,
            threshold_breached=False,
            sensor_status=SensorStatus.ACTIVE,
            raw_metadata={"gas_species": species},
        ),
    )


def _worker_event(zone_id: str, worker_id: str, kind: WorkerEventKind, ppe_status: dict[str, bool] | None) -> WorkerEventV1:
    return WorkerEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.now(timezone.utc),
        correlation_id=uuid.uuid4(),
        causation_id=None,
        producer_service="demo-generator",
        producer_version="1.0",
        site_id=SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=None,
        metadata=_meta(),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind, ppe_status=ppe_status),
    )


def _permit_event(zone_id: str, permit_id: str, permit_type: PermitType, status: PermitStatus, worker_id: str) -> PermitEventV1:
    now = datetime.now(timezone.utc)
    return PermitEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=now,
        correlation_id=uuid.uuid4(),
        causation_id=None,
        producer_service="demo-generator",
        producer_version="1.0",
        site_id=SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=None,
        metadata=_meta(),
        payload=PermitEventPayload(
            permit_id=permit_id,
            permit_type=permit_type,
            status=status,
            issued_to_worker_id=worker_id,
            valid_from=now,
            valid_until=now + timedelta(hours=4),
        ),
    )


def run_scenario_normal(producer: Any) -> None:
    logger.info("Executing Scenario 1: NORMAL")
    for zone in ["ZONE-A", "ZONE-B", "ZONE-C"]:
        producer.publish("sentinel.sensor.events.v1", _sensor_event(zone, SensorType.TEMPERATURE, 22.0, "C", f"TEMP-{zone}"))
        producer.publish("sentinel.sensor.events.v1", _gas_event(zone, "methane", 10.0, "ppm", f"GAS-{zone}"))
        producer.publish("sentinel.worker.events.v1", _worker_event(zone, f"W-{zone}-1", WorkerEventKind.ZONE_ENTRY, {"helmet": True, "vest": True, "gloves": True}))


def run_scenario_gas_rise(producer: Any) -> None:
    logger.info("Executing Scenario 2: GAS-RISE (Single-Zone Gas Hazard)")
    run_scenario_normal(producer)
    time.sleep(0.5)
    producer.publish("sentinel.sensor.events.v1", _gas_event("ZONE-A", "methane", 450.0, "ppm", "GAS-ZONE-A"))
    producer.publish("sentinel.sensor.events.v1", _sensor_event("ZONE-A", SensorType.TEMPERATURE, 42.0, "C", "TEMP-ZONE-A"))


def run_scenario_compound_risk(producer: Any) -> None:
    logger.info("Executing Scenario 3: COMPOUND-RISK (Gas + Worker Violation + Hot Work Permit)")
    run_scenario_gas_rise(producer)
    time.sleep(0.5)
    producer.publish("sentinel.permit.events.v1", _permit_event("ZONE-A", "PERMIT-HW-101", PermitType.HOT_WORK, PermitStatus.ACTIVE, "W-ZONE-A-1"))
    producer.publish("sentinel.worker.events.v1", _worker_event("ZONE-A", "W-ZONE-A-2", WorkerEventKind.ZONE_ENTRY, {"helmet": False, "vest": True, "gloves": False}))
    producer.publish("sentinel.sensor.events.v1", _gas_event("ZONE-A", "carbon_monoxide", 65.0, "ppm", "GAS-CO-ZONE-A"))


def run_scenario_multi_zone_emergency(producer: Any) -> None:
    logger.info("Executing Scenario 4: MULTI-ZONE-EMERGENCY")
    run_scenario_compound_risk(producer)
    time.sleep(0.5)

    # Critical methane breach in ZONE-A
    producer.publish("sentinel.sensor.events.v1", _gas_event("ZONE-A", "methane", 1800.0, "ppm", "GAS-ZONE-A-CRIT"))
    producer.publish("sentinel.sensor.events.v1", _gas_event("ZONE-A", "hydrogen_sulfide", 45.0, "ppm", "GAS-H2S-ZONE-A"))
    producer.publish("sentinel.sensor.events.v1", _sensor_event("ZONE-A", SensorType.TEMPERATURE, 68.0, "C", "TEMP-ZONE-A"))

    # Secondary propagation into ZONE-B (shared ventilation)
    producer.publish("sentinel.sensor.events.v1", _gas_event("ZONE-B", "methane", 600.0, "ppm", "GAS-ZONE-B-VENT"))
    producer.publish("sentinel.worker.events.v1", _worker_event("ZONE-B", "W-ZONE-B-1", WorkerEventKind.ZONE_ENTRY, {"helmet": True, "vest": True, "gloves": True}))

    # Secondary propagation into ZONE-C (connected route)
    producer.publish("sentinel.worker.events.v1", _worker_event("ZONE-C", "W-ZONE-C-1", WorkerEventKind.ZONE_ENTRY, {"helmet": True, "vest": False, "gloves": True}))


def reset_demo_state(redis_client: Any | None, state_cache: Any | None, orchestrator_publisher: Any | None) -> None:
    logger.info("Resetting demo state")
    if redis_client:
        try:
            for key in redis_client.scan_iter(match="sentinel:*"):
                redis_client.delete(key)
        except Exception as e:
            logger.warning("Redis reset error: %s", e)

    if state_cache and hasattr(state_cache, "clear"):
        state_cache.clear()

    if orchestrator_publisher and hasattr(orchestrator_publisher, "clear"):
        orchestrator_publisher.clear()
