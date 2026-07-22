"""
data_engine_adapter.py

Adapts Sentinel_Data_Engine's MasterEventGenerator (a separate, external
project -- richer, physically-correlated fake data than this harness's own
random-value simulators) onto the REAL SENTINEL contracts
(SensorEventV1/WorkerEventV1/PermitEventV1), so its output can be
published through the real, unmodified EventProducer/KafkaTransport and
consumed by the real agents exactly like the original simulators' output.

Nothing in Sentinel_Data_Engine is modified -- this file is the only place
that knows about both codebases' shapes. Everything else in this harness
stays unaware Sentinel_Data_Engine exists at all.

One shared MasterEventGenerator drives sensor+worker+permit events
together on purpose: its PlantState/timeline/scenario are shared,
evolving state -- running three separate generator instances (one per
simulator process) would give each an independently random, uncorrelated
timeline and defeat the entire point of "physically correlated realistic
data." See fake_data_engine_simulator.py, the single process that ticks
this adapter and publishes everything it yields.

Known, deliberate lossy mappings (documented here, not hidden):

  - Sentinel_Data_Engine's "Flame Detector" reading has no equivalent in
    the real SensorType enum (GAS/TEMPERATURE/PRESSURE/VIBRATION/
    PROXIMITY/SMOKE/HUMIDITY -- no FLAME). Mapped to SensorType.SMOKE,
    with the original type preserved in
    raw_metadata["data_engine_sensor_type"] so nothing is silently lost.
  - "Machine Temperature" also has no distinct real type; mapped to
    SensorType.TEMPERATURE with the same raw_metadata preservation.
  - PermitType values "chemical", "radiation", "cold_work", "line_break"
    have no real PermitType equivalent (real enum: HOT_WORK/
    CONFINED_SPACE/ELECTRICAL/HEIGHT/EXCAVATION/LIFTING). Permits of those
    types are skipped, not force-mapped to something misleading -- each
    skip is logged once via event_logger, not silently dropped.
  - The real WorkerEventPayload has no field for raw biometric VALUES
    (heart rate, body temp, fatigue, SpO2) -- only event_kind (including
    BIOMETRIC_ALERT), ppe_status, and location. When Sentinel_Data_Engine's
    biometrics cross an alert threshold, this adapter emits a
    BIOMETRIC_ALERT event -- it cannot carry the actual vitals number,
    because the contract has nowhere to put it.
  - The real GeoLocation is WGS84 latitude/longitude. Sentinel_Data_Engine's
    worker location is a local plant grid (x/y/floor/accuracy_m) --
    semantically different units, not a unit conversion. Rather than
    fabricate fake GPS coordinates from plant-grid coordinates, `location`
    is left unset on every mapped WorkerEvent.
  - PermitConditionRef.is_satisfied isn't tracked by Sentinel_Data_Engine's
    permit model at all; approximated as True when the permit's
    lifecycle_status is "active"/"pending_approval", False otherwise --
    a heuristic on our side, not sourced data. Documented, not hidden.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import harness_config as cfg

cfg.bootstrap_data_engine_sys_path()

from generators.master_event_generator import MasterEventGenerator  # noqa: E402
from events.permit_event import PermitEvent as DEPermitEvent  # noqa: E402
from events.sensor_event import SensorEvent as DESensorEvent  # noqa: E402
from events.worker_event import WorkerEvent as DEWorkerEvent  # noqa: E402

cfg.bootstrap_agent_sys_path()  # adds sentinel_contracts; no name collisions with the above (verified)

from sentinel_contracts.common.metadata import Environment, Metadata  # noqa: E402
from sentinel_contracts.events.permit_event_v1 import (  # noqa: E402
    PermitConditionRef, PermitEventPayload, PermitEventV1, PermitStatus, PermitType,
)
from sentinel_contracts.events.sensor_event_v1 import (  # noqa: E402
    SensorEventPayload, SensorEventV1, SensorStatus, SensorType,
)
from sentinel_contracts.events.worker_event_v1 import (  # noqa: E402
    WorkerEventKind, WorkerEventPayload, WorkerEventV1,
)

from event_logger import StageEvent, log_stage  # noqa: E402

# Sentinel_Data_Engine sensor_type string -> real SensorType enum.
# "Flame Detector" and "Machine Temperature" have no real equivalent -- see module docstring.
SENSOR_TYPE_MAP = {
    "Gas Sensor": SensorType.GAS,
    "Temperature Sensor": SensorType.TEMPERATURE,
    "Humidity Sensor": SensorType.HUMIDITY,
    "Pressure Sensor": SensorType.PRESSURE,
    "Machine Temperature": SensorType.TEMPERATURE,
    "Vibration Sensor": SensorType.VIBRATION,
    "Smoke Detector": SensorType.SMOKE,
    "Flame Detector": SensorType.SMOKE,
}

# Sentinel_Data_Engine permit_type -> real PermitType. Types with no real
# equivalent (chemical/radiation/cold_work/line_break) are simply absent
# here; build_permit_event() skips and logs anything not in this map.
PERMIT_TYPE_MAP = {
    "hot_work": PermitType.HOT_WORK,
    "confined_space": PermitType.CONFINED_SPACE,
    "electrical": PermitType.ELECTRICAL,
    "height": PermitType.HEIGHT,
    "excavation": PermitType.EXCAVATION,
}

# Sentinel_Data_Engine lifecycle_status -> real PermitStatus.
PERMIT_STATUS_MAP = {
    "draft": PermitStatus.REQUESTED,
    "pending_approval": PermitStatus.APPROVED,
    "active": PermitStatus.ACTIVE,
    "suspended": PermitStatus.SUSPENDED,
    "revoked": PermitStatus.CLOSED,
    "expired": PermitStatus.EXPIRED,
}

# Biometric alert thresholds -- Sentinel_Data_Engine doesn't define these
# itself (its worker_generator just emits raw values every tick); chosen
# here as reasonable occupational-health defaults so BIOMETRIC_ALERT
# actually means something, not fired on every tick.
HEART_RATE_ALERT_BPM = 130.0
FATIGUE_ALERT_INDEX = 0.85
SPO2_ALERT_PCT = 92.0

_unmapped_permit_types_logged: set[str] = set()


def _new_correlation() -> uuid.UUID:
    return uuid.uuid4()


def _metadata() -> Metadata:
    return Metadata(schema_id=1, schema_version=1, environment=Environment.DEV,
                     tags={"source": "Sentinel_Data_Engine"})


def map_sensor_event(de_event: DESensorEvent) -> SensorEventV1:
    p = de_event.payload
    real_type = SENSOR_TYPE_MAP.get(p["sensor_type"])
    if real_type is None:
        raise ValueError(f"unmapped Data Engine sensor_type: {p['sensor_type']!r}")
    correlation_id = _new_correlation()
    raw_metadata = {}
    if p["sensor_type"] in ("Flame Detector", "Machine Temperature"):
        raw_metadata["data_engine_sensor_type"] = p["sensor_type"]

    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.fromisoformat(de_event.timestamp),
        correlation_id=correlation_id,
        producer_service="integration-testing-data-engine-adapter",
        producer_version="1.0.0",
        site_id=de_event.site_id,
        zone_id=de_event.zone_id,
        partition_key=de_event.zone_id,
        trace_id=str(correlation_id),
        metadata=_metadata(),
        payload=SensorEventPayload(
            sensor_id=p["sensor_id"], sensor_type=real_type, value=float(p["value"]), unit=p["unit"],
            threshold_breached=(p["status"] != "Normal"), sensor_status=SensorStatus.ACTIVE,
            raw_metadata=raw_metadata,
        ),
    )


def map_worker_events(de_event: DEWorkerEvent, prev_zone: str | None, prev_ppe: dict | None,
                       emit_ppe_heartbeat: bool) -> list[WorkerEventV1]:
    """One Data Engine worker-location tick can fan out into several real
    events: a ZONE_EXIT/ZONE_ENTRY pair on zone change, a PPE_STATUS event
    on any violation (or periodically as a heartbeat), and a
    BIOMETRIC_ALERT when vitals cross threshold. Returns [] if nothing
    real happened this tick -- not every Data Engine tick needs to become
    a Kafka message."""
    p = de_event.payload
    worker_id = p["worker_id"]
    zone_id = de_event.zone_id
    out: list[WorkerEventV1] = []

    def _build(event_kind: WorkerEventKind, ppe_status: dict | None, zone: str) -> WorkerEventV1:
        correlation_id = _new_correlation()
        return WorkerEventV1(
            event_id=uuid.uuid4(), event_timestamp=datetime.fromisoformat(de_event.timestamp),
            correlation_id=correlation_id, producer_service="integration-testing-data-engine-adapter",
            producer_version="1.0.0", site_id=de_event.site_id, zone_id=zone, partition_key=zone,
            trace_id=str(correlation_id), metadata=_metadata(),
            payload=WorkerEventPayload(worker_id=worker_id, event_kind=event_kind, ppe_status=ppe_status),
        )

    if prev_zone is not None and prev_zone != zone_id:
        out.append(_build(WorkerEventKind.ZONE_EXIT, None, prev_zone))
        out.append(_build(WorkerEventKind.ZONE_ENTRY, None, zone_id))
    elif prev_zone is None:
        out.append(_build(WorkerEventKind.ZONE_ENTRY, None, zone_id))

    ppe = p.get("ppe_status", {})
    ppe_violation = any(v is False for v in ppe.values())
    if ppe_violation or emit_ppe_heartbeat:
        out.append(_build(WorkerEventKind.PPE_STATUS, dict(ppe), zone_id))

    bio = p.get("biometrics", {})
    if (bio.get("heart_rate", 0) >= HEART_RATE_ALERT_BPM
            or bio.get("fatigue_index", 0) >= FATIGUE_ALERT_INDEX
            or bio.get("spo2", 100) <= SPO2_ALERT_PCT):
        out.append(_build(WorkerEventKind.BIOMETRIC_ALERT, None, zone_id))

    return out


def map_permit_event(de_event: DEPermitEvent) -> PermitEventV1 | None:
    p = de_event.payload
    real_type = PERMIT_TYPE_MAP.get(p["permit_type"])
    if real_type is None:
        if p["permit_type"] not in _unmapped_permit_types_logged:
            _unmapped_permit_types_logged.add(p["permit_type"])
            log_stage(StageEvent(
                component="Permit Simulator (Data Engine)", stage="PermitEvent Type Unmapped", status="skipped",
                reason=f"Data Engine permit_type={p['permit_type']!r} has no equivalent in the real "
                       f"PermitType enum (HOT_WORK/CONFINED_SPACE/ELECTRICAL/HEIGHT/EXCAVATION/LIFTING). "
                       f"Skipping this permit type for the rest of the run (logged once).",
            ))
        return None

    real_status = PERMIT_STATUS_MAP.get(p["lifecycle_status"], PermitStatus.REQUESTED)
    conditions = [
        PermitConditionRef(condition_id=f"COND-{i}", description=desc,
                            is_satisfied=p["lifecycle_status"] in ("active", "pending_approval"))
        for i, desc in enumerate(p.get("conditions", []))
    ]
    correlation_id = _new_correlation()
    return PermitEventV1(
        event_id=uuid.uuid4(), event_timestamp=datetime.fromisoformat(de_event.timestamp),
        correlation_id=correlation_id, producer_service="integration-testing-data-engine-adapter",
        producer_version="1.0.0", site_id=de_event.site_id, zone_id=de_event.zone_id,
        partition_key=de_event.zone_id, trace_id=str(correlation_id), metadata=_metadata(),
        payload=PermitEventPayload(
            permit_id=p["permit_id"], permit_type=real_type, status=real_status,
            issued_to_worker_id=p["issued_to"], valid_from=datetime.fromisoformat(p["valid_from"]),
            valid_until=datetime.fromisoformat(p["valid_until"]), conditions=conditions,
        ),
    )


class DataEngineAdapter:
    def __init__(self, site_id: str):
        self._gen = MasterEventGenerator(site_id=site_id)
        self._worker_zone: dict[str, str] = {}
        self._ppe_heartbeat_counter = 0

    def tick(self) -> list[tuple[object, str]]:
        """Returns [(real_pydantic_event, kafka_topic), ...] for exactly
        this tick -- every event the real Kafka topics should receive,
        already mapped and ready to publish as-is."""
        raw = self._gen.tick()
        out: list[tuple[object, str]] = []
        self._ppe_heartbeat_counter += 1
        emit_ppe_heartbeat = (self._ppe_heartbeat_counter % 8 == 0)

        for de_event in raw["events"]:
            if isinstance(de_event, DESensorEvent):
                try:
                    out.append((map_sensor_event(de_event), cfg.TOPIC_SENSOR_EVENTS))
                except ValueError as e:
                    log_stage(StageEvent(component="Sensor Simulator (Data Engine)", stage="Mapping Error",
                                          status="failed", reason=str(e)))
            elif isinstance(de_event, DEWorkerEvent):
                worker_id = de_event.payload["worker_id"]
                prev_zone = self._worker_zone.get(worker_id)
                mapped = map_worker_events(de_event, prev_zone, None, emit_ppe_heartbeat)
                self._worker_zone[worker_id] = de_event.zone_id
                for real_event in mapped:
                    out.append((real_event, cfg.TOPIC_WORKER_EVENTS))
            elif isinstance(de_event, DEPermitEvent):
                mapped = map_permit_event(de_event)
                if mapped is not None:
                    out.append((mapped, cfg.TOPIC_PERMIT_EVENTS))
            # Everything else (EnvironmentalEvent, EquipmentStateEvent, IncidentEvent,
            # AgentResultEvent, RiskEvent, ActionRequest/ResultEvent) has no real Kafka
            # topic to go to today -- see README's platform-gaps table. Not an error,
            # just not this harness's concern; left unpublished on purpose.

        return out
