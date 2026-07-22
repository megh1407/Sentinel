"""
acceptance_check.py

NOT a pytest file -- a standalone, human-readable checklist that verifies
Zone Intelligence Agent actually does its job, point by point, matching the
plain-English job description:

    1. Keeps a live, accurate picture of each zone (occupancy, sensors,
       permits, equipment, incidents) that updates in real time.
    2. Checks that picture against 8 danger rules after every update.
    3. When a rule trips, publishes an anomaly with a reason, a confidence
       score, and evidence -- never just a bare alarm.
    4. NEVER takes direct action (no equipment control, no commands) --
       only ever publishes ZoneState / ZoneAnomalyDetected for other
       agents to act on.

Run it directly:

    cd agents/zone_intelligence_agent
    PYTHONPATH=../..:../../libs:../../sentinel_contracts:. python3 acceptance_check.py

Requires a real Redis at localhost:6379. Each check is independent -- one
failing doesn't stop the rest from running, so you get a full report.
"""
import datetime
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
from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1
from sentinel_eventbus import EventProducer, InMemoryTransport, LocalSchemaProvider
from sentinel_state import StateContainer
from zone_intelligence_agent import ZoneIntelligenceAgent

SITE_ID = "SITE-01"
RESULTS = []  # (description, passed: bool, detail: str)


def check(description):
    """Decorator: runs a check function, catches any failure (assertion or
    exception), and records a PASS/FAIL line -- one bad check never stops
    the rest of the report from running."""
    def wrapper(fn):
        try:
            detail = fn()
            RESULTS.append((description, True, detail or "ok"))
        except AssertionError as e:
            RESULTS.append((description, False, str(e)))
        except Exception as e:
            RESULTS.append((description, False, f"CRASHED: {type(e).__name__}: {e}"))
        return fn
    return wrapper


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _meta():
    return Metadata(schema_id=101, schema_version=1, environment=Environment.DEV)


def worker_event(zone_id, worker_id, kind=WorkerEventKind.ZONE_ENTRY):
    return WorkerEventV1(event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
                          producer_service="worker-tracking", producer_version="1.0.0", site_id=SITE_ID,
                          zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
                          payload=WorkerEventPayload(worker_id=worker_id, event_kind=kind))


def sensor_event(zone_id, sensor_id, value, breached):
    return SensorEventV1(event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
                          producer_service="env-ingestion", producer_version="1.0.0", site_id=SITE_ID,
                          zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
                          payload=SensorEventPayload(sensor_id=sensor_id, sensor_type=SensorType.GAS, value=value,
                                                      unit="ppm", threshold_breached=breached))


def permit_event(zone_id, permit_id, permit_type, status=PermitStatus.ACTIVE):
    now = _now()
    return PermitEventV1(event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(),
                          producer_service="permit-system", producer_version="1.0.0", site_id=SITE_ID,
                          zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
                          payload=PermitEventPayload(permit_id=permit_id, permit_type=permit_type, status=status,
                                                      issued_to_worker_id=str(uuid.uuid4()),
                                                      valid_from=now, valid_until=now))


def equipment_risk_event(zone_id, asset_id):
    from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
    from sentinel_contracts.common.explanation_object import ExplanationObject
    now = _now()
    return EquipmentRiskDetectedV1(
        event_id=uuid.uuid4(), event_timestamp=now, correlation_id=uuid.uuid4(), producer_version="1.0.0",
        site_id=SITE_ID, zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
        explanation=ExplanationObject(summary="upstream", generated_at=now, evidence=[],
                                       confidence=ConfidenceScore(value=0.9, derivation=ConfidenceDerivation.RULE_BASED)),
        payload=EquipmentRiskDetectedPayload(asset_id=asset_id, risk_type=EquipmentRiskType.ABNORMAL_TEMPERATURE),
    )


def incident_event(zone_id, incident_id):
    return IncidentEventV1(event_id=uuid.uuid4(), event_timestamp=_now(), correlation_id=uuid.uuid4(),
                            producer_service="incident-system", producer_version="1.0.0", site_id=SITE_ID,
                            zone_id=zone_id, partition_key=zone_id, metadata=_meta(),
                            payload=IncidentEventPayload(incident_id=incident_id, incident_type="SLIP_FALL",
                                                          severity=IncidentSeverity.MINOR))


def new_agent_and_zone():
    """Fresh agent + fresh, never-before-used zone_id for each check, so
    checks can't contaminate each other."""
    redis_client = redis.Redis(host="localhost", port=6379)
    state = StateContainer(redis_client=redis_client)
    agent = ZoneIntelligenceAgent()
    producer = EventProducer(InMemoryTransport(client_id="check"), LocalSchemaProvider())
    agent.container = build_container("ZoneIntelligenceAgent", state, producer)
    agent.initialize()
    zone_id = f"Z-CHECK-{uuid.uuid4().hex[:6]}"
    return agent, zone_id


def anomaly_of_type(results, anomaly_type_str):
    return next((r for r in results if isinstance(r, ZoneAnomalyDetectedV1)
                 and r.payload.anomaly_type.value == anomaly_type_str), None)


def zone_state_of(results):
    return next((r for r in results if isinstance(r, ZoneStateV1)), None)


# ---------------------------------------------------------------------------
# JOB PART 1: keeps a live, accurate picture of the zone
# ---------------------------------------------------------------------------

@check("Job part 1a: occupancy count reflects actual worker entries/exits")
def _():
    agent, zone = new_agent_and_zone()
    agent.process(worker_event(zone, "W-1"))
    agent.process(worker_event(zone, "W-2"))
    results = agent.process(worker_event(zone, "W-1", kind=WorkerEventKind.ZONE_EXIT))
    state = zone_state_of(results)
    assert state.payload.occupancy_count == 1, f"expected 1 worker left, got {state.payload.occupancy_count}"
    return f"occupancy correctly went 1 -> 2 -> 1 after entry/entry/exit"


@check("Job part 1b: sensor breach is reflected in the live picture")
def _():
    agent, zone = new_agent_and_zone()
    results = agent.process(sensor_event(zone, "GAS-1", value=900, breached=True))
    state = zone_state_of(results)
    assert "GAS-1" in state.payload.active_sensor_alert_ids, "breaching sensor not reflected in zone state"
    return "active_sensor_alert_ids correctly includes the breaching sensor"


@check("Job part 1c: an unrelated observer can read the SAME live picture back from Redis")
def _():
    # Proves the "picture" is actually shared/live, not just a private in-memory
    # variable inside one agent instance -- a second, independent connection
    # should see exactly what the agent just wrote.
    agent, zone = new_agent_and_zone()
    agent.process(worker_event(zone, "W-1"))
    independent_redis = redis.Redis(host="localhost", port=6379)
    raw = independent_redis.get(f"sentinel:zone:state:{zone}")
    assert raw is not None, "a second, independent Redis connection could not see the zone state at all"
    assert b'"occupancy_count":1' in raw, "independently-read state doesn't show the worker that just entered"
    return "a second, independent Redis client reads back the exact same live state"


# ---------------------------------------------------------------------------
# JOB PART 2: checks the 8 danger rules after every update
# ---------------------------------------------------------------------------

@check("Rule 1: too many workers -> OCCUPANCY_EXCEEDED")
def _():
    agent, zone = new_agent_and_zone()
    for i in range(10):
        agent.process(worker_event(zone, f"W-{i}"))
    results = agent.process(worker_event(zone, "W-EXTRA"))
    anomaly = anomaly_of_type(results, "OCCUPANCY_EXCEEDED")
    assert anomaly is not None, "11th worker did not trigger OCCUPANCY_EXCEEDED"
    return anomaly.explanation.summary


@check("Rule 2: dangerous sensor reading -> ENVIRONMENTAL_HAZARD")
def _():
    agent, zone = new_agent_and_zone()
    results = agent.process(sensor_event(zone, "GAS-1", value=900, breached=True))
    anomaly = anomaly_of_type(results, "ENVIRONMENTAL_HAZARD")
    assert anomaly is not None, "breached sensor reading did not trigger ENVIRONMENTAL_HAZARD"
    return anomaly.explanation.summary


@check("Rule 3: conflicting permits (Hot Work + Confined Space) -> PERMIT_CONFLICT")
def _():
    agent, zone = new_agent_and_zone()
    agent.process(permit_event(zone, "P-HOT", PermitType.HOT_WORK))
    results = agent.process(permit_event(zone, "P-CONFINED", PermitType.CONFINED_SPACE))
    anomaly = anomaly_of_type(results, "PERMIT_CONFLICT")
    assert anomaly is not None, "Hot Work + Confined Space together did not trigger PERMIT_CONFLICT"
    return anomaly.explanation.summary


@check("Rule 3 (negative control): NON-conflicting permits do NOT trigger PERMIT_CONFLICT")
def _():
    agent, zone = new_agent_and_zone()
    agent.process(permit_event(zone, "P-HOT", PermitType.HOT_WORK))
    results = agent.process(permit_event(zone, "P-ELEC", PermitType.ELECTRICAL))
    anomaly = anomaly_of_type(results, "PERMIT_CONFLICT")
    assert anomaly is None, "Hot Work + Electrical incorrectly triggered PERMIT_CONFLICT (false positive!)"
    return "correctly did NOT flag a harmless permit combination"


@check("Rule 4: too many incidents -> INCIDENT_FREQUENCY_EXCEEDED")
def _():
    agent, zone = new_agent_and_zone()
    for i in range(3):
        agent.process(incident_event(zone, f"INC-{i}"))
    results = agent.process(incident_event(zone, "INC-EXTRA"))
    anomaly = anomaly_of_type(results, "INCIDENT_FREQUENCY_EXCEEDED")
    assert anomaly is not None, "4th distinct incident did not trigger INCIDENT_FREQUENCY_EXCEEDED"
    return anomaly.explanation.summary


@check("Rule 5: equipment risk WHILE workers present -> ZONE_HEALTH_DEGRADED")
def _():
    agent, zone = new_agent_and_zone()
    agent.process(worker_event(zone, "W-1"))  # zone occupied first
    results = agent.process(equipment_risk_event(zone, "EQ-1"))
    anomaly = anomaly_of_type(results, "ZONE_HEALTH_DEGRADED")
    assert anomaly is not None, "equipment risk in an occupied zone did not trigger ZONE_HEALTH_DEGRADED"
    return anomaly.explanation.summary


@check("Rule 5 (negative control): equipment risk in an EMPTY zone does NOT trigger it")
def _():
    agent, zone = new_agent_and_zone()
    results = agent.process(equipment_risk_event(zone, "EQ-1"))  # nobody in the zone
    anomaly = anomaly_of_type(results, "ZONE_HEALTH_DEGRADED")
    assert anomaly is None, "equipment risk with ZERO workers present incorrectly triggered ZONE_HEALTH_DEGRADED"
    return "correctly did NOT flag equipment risk in an empty, unoccupied zone"


@check("Rule 6: sensor gone silent -> MISSING_SENSOR_DATA (partial, documented limitation)")
def _():
    agent, zone = new_agent_and_zone()
    t0 = _now()
    agent.process(sensor_event(zone, "GAS-1", value=100, breached=False))
    later_event = worker_event(zone, "W-1")
    later_event.event_timestamp = t0 + datetime.timedelta(minutes=15)  # past the 10-min staleness window
    results = agent.process(later_event)
    anomaly = anomaly_of_type(results, "MISSING_SENSOR_DATA")
    assert anomaly is not None, "a sensor silent for 15 minutes was not flagged (only checked opportunistically)"
    return anomaly.explanation.summary + " [NOTE: only detected because another event touched the zone -- see known gap]"


@check("Rule 7: rapid state change -> RAPID_STATE_CHANGE")
def _():
    agent, zone = new_agent_and_zone()
    results = None
    for i in range(9):
        results = agent.process(worker_event(zone, f"W-{i}"))
    anomaly = anomaly_of_type(results, "RAPID_STATE_CHANGE")
    assert anomaly is not None, "9 state changes in under 5 minutes did not trigger RAPID_STATE_CHANGE"
    return anomaly.explanation.summary


@check("Rule 8: repeated/stacking anomalies -> REPEATED_ANOMALIES")
def _():
    agent, zone = new_agent_and_zone()
    results = None
    for i in range(4):
        results = agent.process(sensor_event(zone, f"GAS-{i}", value=900, breached=True))
    anomaly = anomaly_of_type(results, "REPEATED_ANOMALIES")
    assert anomaly is not None, "4 distinct anomalies within an hour did not trigger REPEATED_ANOMALIES"
    return anomaly.explanation.summary


# ---------------------------------------------------------------------------
# JOB PART 3: every anomaly comes with a reason, confidence, and evidence
# ---------------------------------------------------------------------------

@check("Every anomaly includes a non-empty explanation, a confidence score, AND evidence")
def _():
    agent, zone = new_agent_and_zone()
    results = agent.process(sensor_event(zone, "GAS-1", value=900, breached=True))
    anomaly = anomaly_of_type(results, "ENVIRONMENTAL_HAZARD")
    assert anomaly.explanation.summary.strip() != "", "explanation summary is empty"
    assert 0.0 <= anomaly.explanation.confidence.value <= 1.0, "confidence score out of range"
    assert len(anomaly.explanation.evidence) > 0, "no evidence attached to the anomaly"
    return (f"summary='{anomaly.explanation.summary[:50]}...', "
            f"confidence={anomaly.explanation.confidence.value}, evidence_items={len(anomaly.explanation.evidence)}")


# ---------------------------------------------------------------------------
# JOB PART 4: the agent NEVER takes direct action -- only ever publishes
# ZoneState / ZoneAnomalyDetected, nothing else
# ---------------------------------------------------------------------------

@check("Agent output is ALWAYS one of exactly two types -- never a direct command/action")
def _():
    agent, zone = new_agent_and_zone()
    all_results = []
    all_results += agent.process(worker_event(zone, "W-1"))
    all_results += agent.process(sensor_event(zone, "GAS-1", value=900, breached=True))
    all_results += agent.process(permit_event(zone, "P-1", PermitType.HOT_WORK))
    allowed_types = {"ZoneStateV1", "ZoneAnomalyDetectedV1"}
    seen_types = {type(r).__name__ for r in all_results}
    assert seen_types <= allowed_types, f"agent produced an unexpected output type: {seen_types - allowed_types}"
    return f"across {len(all_results)} outputs, only saw: {seen_types}"


def main():
    try:
        redis.Redis(host="localhost", port=6379).ping()
    except redis.ConnectionError:
        print("ERROR: no Redis reachable at localhost:6379 -- this check requires it. Exiting.")
        sys.exit(1)

    print("=" * 78)
    print("ZONE INTELLIGENCE AGENT -- JOB ACCEPTANCE CHECK")
    print("=" * 78)
    for description, passed, detail in RESULTS:
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {description}")
        print(f"       {detail}")
    print("=" * 78)
    total = len(RESULTS)
    passed_count = sum(1 for _, p, _ in RESULTS if p)
    print(f"{passed_count}/{total} checks passed")
    if passed_count < total:
        print("\nFAILED CHECKS:")
        for description, passed, detail in RESULTS:
            if not passed:
                print(f"  - {description}\n    reason: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
