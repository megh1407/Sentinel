"""
fake_equipment_simulator.py

Does NOT publish equipment/maintenance events, and this is deliberate, not
an oversight -- verified by reading the actual repo, not assumed:

  - contracts/topics/kafka_topics.yaml registers sentinel.equipment.state.v1
    (schema: equipment_state), but there is no generated Pydantic model for
    it anywhere under sentinel_contracts/events/ -- only a legacy
    contracts/events/v1/equipment_state.schema.json (plain JSON Schema, not
    an Avro contract with a codegen'd class). `grep -rl "class EquipmentState"`
    across the repo returns nothing.
  - agents/zone_intelligence_agent/main.py's own module docstring documents
    this exact gap under INPUT_TOPICS: "no generated Pydantic model exists
    for its `equipment_state` schema anywhere in sentinel_contracts ...
    Not subscribed."
  - EquipmentRiskDetectedV1 and MaintenanceRequiredV1 DO have real generated
    models (equipment_risk_detected_v1.py, maintenance_required_v1.py) and
    ZoneIntelligenceAgent.process() genuinely handles both -- but main.py
    doesn't subscribe to either topic in production because kafka_topics.yaml
    has no registered topic entry for them at all (see main.py's
    PLATFORM_GAP block). There is no legal topic name to publish to.

Rather than invent a topic/schema myself (explicitly out of scope -- "DO
NOT modify ... contracts ... schemas ... topics ... registry") or silently
do nothing with no record of why, this script logs one INFO-level gap entry
to the shared trace store and exits 0. failure_report.py reads this back
and lists it under Platform Gaps, not under Failures -- it is not something
that broke, it is something that was never wired.

If EquipmentRiskDetectedV1/MaintenanceRequiredV1 ever get real registry
topic entries, a real simulator for them can be written the same way
fake_worker_simulator.py / fake_permit_simulator.py already are -- the
Pydantic models already exist and are already fully handled by
ZoneIntelligenceAgent.process(); only the topic registration is missing.
"""
from __future__ import annotations

import sys

from event_logger import StageEvent, log_stage


def main() -> int:
    reason = (
        "sentinel.equipment.state.v1 has no generated Pydantic model (only a legacy "
        "JSON Schema file, contracts/events/v1/equipment_state.schema.json); "
        "EquipmentRiskDetected/MaintenanceRequired have real models but no registered "
        "Kafka topic in contracts/topics/kafka_topics.yaml -- see "
        "agents/zone_intelligence_agent/main.py's module docstring, PLATFORM_GAP section."
    )
    log_stage(StageEvent(
        component="Equipment Simulator", stage="Simulator Start", status="skipped", reason=reason,
    ))
    print("[Equipment Simulator] not starting -- platform gap, not a bug. See this file's module docstring.")
    print(f"  {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
