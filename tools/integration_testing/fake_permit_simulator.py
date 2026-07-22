"""
fake_permit_simulator.py

Publishes real PermitEventV1 events through the real EventProducer +
KafkaTransport. Feeds sentinel.permit.events.v1, which Zone Intelligence
Agent genuinely consumes (PERMIT_CONFLICT detection when two active
permits in the same zone belong to a conflicting type pair -- see
_handle_permit_event / CONFLICTING_PERMIT_TYPE_PAIRS).

Occasionally issues both a HOT_WORK and a CONFINED_SPACE permit active in
the same zone at once on purpose, since that's the one conflict pair the
agent actually checks for -- this is the harness manufacturing a scenario
to prove the rule fires, not a bug.

Usage:
    python3 fake_permit_simulator.py [--iterations N]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import harness_config as cfg

cfg.bootstrap_agent_sys_path()

from sentinel_contracts.common.metadata import Environment, Metadata  # noqa: E402
from sentinel_contracts.events.permit_event_v1 import (  # noqa: E402
    PermitEventPayload, PermitEventV1, PermitStatus, PermitType,
)
from sentinel_eventbus import EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

CONFLICT_PAIR = (PermitType.HOT_WORK, PermitType.CONFINED_SPACE)
NORMAL_TYPES = [PermitType.ELECTRICAL, PermitType.HEIGHT, PermitType.EXCAVATION, PermitType.LIFTING]


def build_event(zone_id: str, permit_type: PermitType, status: PermitStatus,
                correlation_id: uuid.UUID) -> PermitEventV1:
    # trace_id == str(correlation_id): see fake_sensor_simulator.py's build_event() for why.
    now = datetime.now(timezone.utc)
    return PermitEventV1(
        event_id=uuid.uuid4(),
        event_timestamp=now,
        correlation_id=correlation_id,
        producer_service="integration-testing-permit-simulator",
        producer_version="1.0.0",
        site_id=cfg.SITE_ID,
        zone_id=zone_id,
        partition_key=zone_id,
        trace_id=str(correlation_id),
        metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV),
        payload=PermitEventPayload(
            permit_id=f"PERMIT-{uuid.uuid4().hex[:8]}", permit_type=permit_type, status=status,
            issued_to_worker_id=str(uuid.uuid4()), valid_from=now, valid_until=now + timedelta(hours=8),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--conflict-every", type=int, default=5,
                         help="every Nth iteration deliberately issues the conflicting HOT_WORK+CONFINED_SPACE pair")
    args = parser.parse_args()

    transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="integration-testing-permit-simulator"),
        component="Permit Simulator",
    )
    producer = EventProducer(transport, LocalSchemaProvider())

    i = 0
    print(f"[Permit Simulator] publishing to {cfg.TOPIC_PERMIT_EVENTS}")
    try:
        while args.iterations is None or i < args.iterations:
            zone_id = random.choice(cfg.ZONE_IDS)
            correlation_id = uuid.uuid4()
            trace_id = str(correlation_id)
            permit_types = [random.choice(NORMAL_TYPES)]
            if args.conflict_every and i > 0 and i % args.conflict_every == 0:
                permit_types = list(CONFLICT_PAIR)

            for permit_type in permit_types:
                try:
                    event = build_event(zone_id, permit_type, PermitStatus.ACTIVE, correlation_id)
                    log_stage(StageEvent(
                        component="Permit Simulator", stage="PermitEvent Created", status="success",
                        trace_id=trace_id, correlation_id=str(event.correlation_id), event_id=str(event.event_id),
                        event_type="PermitEvent", schema_version=event.event_version,
                        extra={"zone_id": zone_id, "permit_type": permit_type.value,
                               "deliberate_conflict": len(permit_types) > 1},
                    ))
                    producer.publish(cfg.TOPIC_PERMIT_EVENTS, event, key=zone_id)
                except Exception as e:  # noqa: BLE001
                    log_stage(StageEvent(component="Permit Simulator", stage="PermitEvent Publish", status="failed",
                                          trace_id=trace_id, reason=f"{type(e).__name__}: {e}"))
                    print(f"  FAILED to publish: {e}", file=sys.stderr)
            i += 1
            time.sleep(cfg.PERMIT_EVENT_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        producer.close()
    print(f"[Permit Simulator] stopped after {i} iteration(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
