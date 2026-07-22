"""
fake_worker_simulator.py

Publishes real WorkerEventV1 events through the real EventProducer +
KafkaTransport. Feeds sentinel.worker.events.v1, which Zone Intelligence
Agent genuinely consumes and acts on (occupancy counting, PPE-adjacent
ZONE_HEALTH_DEGRADED correlation) -- see
agents/zone_intelligence_agent/zone_intelligence_agent.py's
_handle_worker_event.

Usage:
    python3 fake_worker_simulator.py [--iterations N]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import harness_config as cfg

cfg.bootstrap_agent_sys_path()

from sentinel_contracts.common.metadata import Environment, Metadata  # noqa: E402
from sentinel_contracts.events.worker_event_v1 import (  # noqa: E402
    WorkerEventKind, WorkerEventPayload, WorkerEventV1,
)
from sentinel_eventbus import EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

# A small fixed roster so ZONE_ENTRY/ZONE_EXIT pairs are coherent (a worker
# that entered can later exit) rather than pure noise.
WORKERS = [f"WORKER-{i:03d}" for i in range(1, 9)]
_worker_zone: dict[str, str] = {}


def next_event_kind(worker_id: str, zone_id: str) -> WorkerEventKind:
    if _worker_zone.get(worker_id) == zone_id:
        return random.choice([WorkerEventKind.ZONE_EXIT, WorkerEventKind.PPE_STATUS])
    return WorkerEventKind.ZONE_ENTRY


def build_event(zone_id: str, worker_id: str, correlation_id: uuid.UUID) -> WorkerEventV1:
    # trace_id == str(correlation_id): see fake_sensor_simulator.py's build_event() for why.
    kind = next_event_kind(worker_id, zone_id)
    if kind == WorkerEventKind.ZONE_ENTRY:
        _worker_zone[worker_id] = zone_id
    elif kind == WorkerEventKind.ZONE_EXIT:
        _worker_zone.pop(worker_id, None)

    ppe_status = None
    if kind == WorkerEventKind.PPE_STATUS:
        ppe_status = {"hard_hat": random.random() > 0.1, "gloves": random.random() > 0.1,
                      "respirator": random.random() > 0.3}

    return WorkerEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        producer_service="integration-testing-worker-simulator",
        producer_version="1.0.0",
        site_id=cfg.SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=str(correlation_id),
        metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV),
        payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind, ppe_status=ppe_status),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=None)
    args = parser.parse_args()

    transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="integration-testing-worker-simulator"),
        component="Worker Simulator",
    )
    producer = EventProducer(transport, LocalSchemaProvider())

    i = 0
    print(f"[Worker Simulator] publishing to {cfg.TOPIC_WORKER_EVENTS}")
    try:
        while args.iterations is None or i < args.iterations:
            zone_id = random.choice(cfg.ZONE_IDS)
            worker_id = random.choice(WORKERS)
            correlation_id = uuid.uuid4()
            trace_id = str(correlation_id)
            try:
                event = build_event(zone_id, worker_id, correlation_id)
                log_stage(StageEvent(
                    component="Worker Simulator", stage="WorkerEvent Created", status="success",
                    trace_id=trace_id, correlation_id=str(event.correlation_id), event_id=str(event.event_id),
                    event_type="WorkerEvent", schema_version=event.event_version,
                    extra={"zone_id": zone_id, "worker_id": worker_id, "kind": event.payload.event_kind.value},
                ))
                producer.publish(cfg.TOPIC_WORKER_EVENTS, event, key=zone_id)
            except Exception as e:  # noqa: BLE001
                log_stage(StageEvent(component="Worker Simulator", stage="WorkerEvent Publish", status="failed",
                                      trace_id=trace_id, reason=f"{type(e).__name__}: {e}"))
                print(f"  FAILED to publish: {e}", file=sys.stderr)
            i += 1
            time.sleep(cfg.WORKER_EVENT_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        producer.close()
    print(f"[Worker Simulator] stopped after {i} event(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
