"""
fake_data_engine_simulator.py

Alternative to running fake_sensor_simulator.py + fake_worker_simulator.py
+ fake_permit_simulator.py separately. One process, one shared
MasterEventGenerator (via data_engine_adapter.DataEngineAdapter), because
splitting it into three processes would give each its own independently
random plant/timeline/scenario state and defeat the entire point of using
a physically-correlated generator in the first place. This being one
process does not violate "everything communicates only through Kafka" --
that requirement is about simulators and agents never calling each other
directly, and it's still true here: this process only ever talks to Kafka,
same as the other three simulators, it just happens to internally source
three event types from one shared state instead of three independent ones.

Usage:
    python3 fake_data_engine_simulator.py [--iterations N] [--tick-seconds 1.0]

Requires DATA_ENGINE_ROOT to point at your Sentinel_Data_Engine checkout
(see harness_config.py / this repo's README) -- fails fast with a clear
message if it doesn't.
"""
from __future__ import annotations

import argparse
import sys
import time

import harness_config as cfg

cfg.bootstrap_agent_sys_path()

from sentinel_eventbus import EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

from data_engine_adapter import DataEngineAdapter  # noqa: E402
from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

COMPONENT_BY_TOPIC = {
    cfg.TOPIC_SENSOR_EVENTS: "Sensor Simulator (Data Engine)",
    cfg.TOPIC_WORKER_EVENTS: "Worker Simulator (Data Engine)",
    cfg.TOPIC_PERMIT_EVENTS: "Permit Simulator (Data Engine)",
}


def _describe_payload(real_event) -> dict:
    """Pulls the same level of per-event detail fake_sensor_simulator.py /
    fake_worker_simulator.py / fake_permit_simulator.py already log into
    `extra`, so reports built from the trace store can tell sensor types
    apart (gas vs temperature vs ...), see PPE/biometric event kinds, and
    see permit types -- regardless of which data source produced the event."""
    p = real_event.payload
    zone_id = getattr(real_event, "zone_id", None)
    if hasattr(p, "sensor_type"):  # SensorEventV1
        return {"zone_id": zone_id, "sensor_id": p.sensor_id, "sensor_type": p.sensor_type.value,
                "value": p.value, "unit": p.unit, "threshold_breached": p.threshold_breached}
    if hasattr(p, "event_kind"):  # WorkerEventV1
        return {"zone_id": zone_id, "worker_id": p.worker_id, "event_kind": p.event_kind.value}
    if hasattr(p, "permit_type"):  # PermitEventV1
        return {"zone_id": zone_id, "permit_id": p.permit_id, "permit_type": p.permit_type.value,
                "status": p.status.value}
    return {"zone_id": zone_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=None, help="stop after N ticks (default: run forever)")
    parser.add_argument("--tick-seconds", type=float, default=1.0)
    args = parser.parse_args()

    transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="integration-testing-data-engine-simulator"),
        component="Data Engine Simulator",
        component_by_topic=COMPONENT_BY_TOPIC,
    )
    producer = EventProducer(transport, LocalSchemaProvider())

    try:
        adapter = DataEngineAdapter(site_id=cfg.SITE_ID)
    except FileNotFoundError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1

    print(f"[Data Engine Simulator] site_id={cfg.SITE_ID}, DATA_ENGINE_ROOT={cfg.DATA_ENGINE_ROOT}")
    i = 0
    total_published = 0
    try:
        while args.iterations is None or i < args.iterations:
            tick_events = adapter.tick()
            for real_event, topic in tick_events:
                component = COMPONENT_BY_TOPIC.get(topic, "Data Engine Simulator")
                trace_id = getattr(real_event, "trace_id", None)
                try:
                    log_stage(StageEvent(
                        component=component, stage=f"{type(real_event).__name__} Created", status="success",
                        trace_id=trace_id, correlation_id=str(real_event.correlation_id),
                        event_id=str(real_event.event_id), event_type=type(real_event).__name__,
                        schema_version=real_event.event_version, extra=_describe_payload(real_event),
                    ))
                    producer.publish(topic, real_event, key=real_event.zone_id)
                    total_published += 1
                except Exception as e:  # noqa: BLE001
                    log_stage(StageEvent(
                        component=component, stage=f"{type(real_event).__name__} Publish", status="failed",
                        trace_id=trace_id, reason=f"{type(e).__name__}: {e}",
                    ))
                    print(f"  FAILED to publish {type(real_event).__name__}: {e}", file=sys.stderr)
            i += 1
            if i % 10 == 0:
                print(f"  tick {i}: {total_published} total events published so far")
            time.sleep(args.tick_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        producer.close()
    print(f"[Data Engine Simulator] stopped after {i} tick(s), {total_published} event(s) published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
