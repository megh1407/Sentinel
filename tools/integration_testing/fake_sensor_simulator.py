"""
fake_sensor_simulator.py

Publishes real SensorEventV1 events (sentinel_contracts.events.sensor_event_v1)
through the real EventProducer + KafkaTransport + LocalSchemaProvider --
identical objects production's ingestion-service would use. Never calls any
agent directly. Scenarios can be changed while running by editing
.state/scenario_control.json's "sensor_scenario" key (this process polls it
every iteration); see harness_config.SCENARIO_CONTROL_PATH.

Usage:
    python3 fake_sensor_simulator.py [--scenario NORMAL] [--iterations N]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import harness_config as cfg

cfg.bootstrap_agent_sys_path()

from sentinel_contracts.common.metadata import Environment, Metadata  # noqa: E402
from sentinel_contracts.events.sensor_event_v1 import (  # noqa: E402
    SensorEventPayload, SensorEventV1, SensorStatus, SensorType,
)
from sentinel_eventbus import EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

SCENARIOS = {
    # name: (sensor_type, unit, value_fn, threshold_breached, sensor_status)
    "NORMAL": (SensorType.TEMPERATURE, "C", lambda: round(random.uniform(18, 24), 1), False, SensorStatus.ACTIVE),
    "GAS_LEAK": (SensorType.GAS, "ppm", lambda: round(random.uniform(400, 900), 1), True, SensorStatus.ACTIVE),
    "FIRE": (SensorType.SMOKE, "obs/m", lambda: round(random.uniform(60, 100), 1), True, SensorStatus.ACTIVE),
    "HIGH_TEMPERATURE": (SensorType.TEMPERATURE, "C", lambda: round(random.uniform(55, 90), 1), True, SensorStatus.ACTIVE),
    "OXYGEN_DROP": (SensorType.GAS, "%vol", lambda: round(random.uniform(12, 17), 1), True, SensorStatus.ACTIVE),
    "CO_INCREASE": (SensorType.GAS, "ppm", lambda: round(random.uniform(150, 400), 1), True, SensorStatus.ACTIVE),
    "H2S_INCREASE": (SensorType.GAS, "ppm", lambda: round(random.uniform(50, 200), 1), True, SensorStatus.ACTIVE),
    "SMOKE": (SensorType.SMOKE, "obs/m", lambda: round(random.uniform(20, 55), 1), True, SensorStatus.ACTIVE),
    "SENSOR_FAILURE": (SensorType.TEMPERATURE, "C", lambda: 0.0, False, SensorStatus.FAULTY),
}


def read_scenario_override(default: str) -> str:
    if cfg.SCENARIO_CONTROL_PATH.exists():
        try:
            data = json.loads(cfg.SCENARIO_CONTROL_PATH.read_text())
            return data.get("sensor_scenario", default)
        except Exception:  # noqa: BLE001 -- a half-written control file must never crash the simulator
            return default
    return default


def build_event(scenario_name: str, zone_id: str, sensor_id: str, correlation_id: uuid.UUID) -> SensorEventV1:
    # trace_id is deliberately set equal to str(correlation_id), not generated independently.
    # Verified by reading producer.py: the headers dict it puts on every Kafka message carries
    # correlation_id, not the domain trace_id payload field -- trace_id only exists inside the
    # Avro-encoded body. TracingTransport can only see headers, so making trace_id ==
    # correlation_id is what makes "follow one trace_id end-to-end through Kafka" actually work,
    # without touching producer.py itself.
    sensor_type, unit, value_fn, breached, status = SCENARIOS[scenario_name]
    return SensorEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        producer_service="integration-testing-sensor-simulator",
        producer_version="1.0.0",
        site_id=cfg.SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=str(correlation_id),
        metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV,
                           tags={"scenario": scenario_name}),
        payload=SensorEventPayload(
            sensor_id=sensor_id, sensor_type=sensor_type, value=value_fn(), unit=unit,
            threshold_breached=breached, sensor_status=status,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="NORMAL", choices=sorted(SCENARIOS))
    parser.add_argument("--iterations", type=int, default=None, help="stop after N events (default: run forever)")
    parser.add_argument("--zone", default=None, help="fix to a single zone instead of rotating")
    args = parser.parse_args()

    transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="integration-testing-sensor-simulator"),
        component="Sensor Simulator",
    )
    producer = EventProducer(transport, LocalSchemaProvider())

    current_scenario = args.scenario
    i = 0
    print(f"[Sensor Simulator] publishing to {cfg.TOPIC_SENSOR_EVENTS}, starting scenario={current_scenario}")
    try:
        while args.iterations is None or i < args.iterations:
            current_scenario = read_scenario_override(current_scenario)
            zone_id = args.zone or random.choice(cfg.ZONE_IDS)
            sensor_id = f"SENSOR-{zone_id}-{(i % 4) + 1:02d}"
            correlation_id = uuid.uuid4()
            trace_id = str(correlation_id)

            with_ev = None
            try:
                event = build_event(current_scenario, zone_id, sensor_id, correlation_id)
                log_stage(StageEvent(
                    component="Sensor Simulator", stage="SensorEvent Created", status="success",
                    trace_id=trace_id, correlation_id=str(event.correlation_id), event_id=str(event.event_id),
                    event_type="SensorEvent", schema_version=event.event_version,
                    extra={"scenario": current_scenario, "zone_id": zone_id, "sensor_id": sensor_id,
                           "value": event.payload.value, "threshold_breached": event.payload.threshold_breached},
                ))
                producer.publish(cfg.TOPIC_SENSOR_EVENTS, event, key=zone_id)
            except Exception as e:  # noqa: BLE001
                log_stage(StageEvent(
                    component="Sensor Simulator", stage="SensorEvent Publish", status="failed",
                    trace_id=trace_id, reason=f"{type(e).__name__}: {e}",
                ))
                print(f"  FAILED to publish scenario={current_scenario}: {e}", file=sys.stderr)

            i += 1
            time.sleep(cfg.SENSOR_EVENT_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        producer.close()
    print(f"[Sensor Simulator] stopped after {i} event(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
