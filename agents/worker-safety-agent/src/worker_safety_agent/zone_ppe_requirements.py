"""
zone_ppe_requirements.py

PLATFORM GAP this file works around (documented, not silently):

Required PPE per zone is a real, frozen field --
`contracts/config-schema/zone.schema.json`'s `required_ppe: string[]` -- but
it is a *configuration* field, not an *event* field. Traced end-to-end:

  - ZoneState (sentinel_contracts/events/zone_state_v1.py, the only
    generated, publishable projection of "what's true about a zone right
    now") has no required_ppe field. Its ZoneStatePayload carries
    occupancy/risk/permit/sensor/maintenance data only.
  - ZoneAnalysis (the other zone-context contract worker_safety_agent's
    agents.yaml entry lists) has no generated Pydantic model anywhere in
    sentinel_contracts/ (same "*_analysis family" gap the platform-wide
    registry audit already flagged in agents.yaml's zone_intelligence_agent
    entry) -- it cannot be consumed even if it carried the field.
  - No `sentinel_config` package exists anywhere in this codebase (checked;
    zone_intelligence_agent/config.py's docstring independently confirms
    this same finding for its own, unrelated, config needs).
  - No client anywhere in this repo reads contracts/config-schema/*.json at
    runtime; that directory is validated JSON Schema for an out-of-repo
    configuration-service, not a library with a Python loader.

So: there is currently no wire mechanism by which a running
worker_safety_agent process could learn "zone Z-104 requires helmet+vest"
from the live platform. This is a real gap, not a design choice -- see
README.md's "Known gaps" section (G1).

Resolution taken here mirrors the exact precedent already established in
this repository for the identical situation (zone_intelligence_agent's own
config.py, whose docstring states: "No sentinel_config package exists
anywhere in this codebase yet ... this is a self-contained,
dependency-free resolver an eventual sentinel_config service could replace
without changing [the] public interface"): a small, internal,
dependency-free lookup that an eventual config-service client can replace
without touching any caller. This is NOT a new wire contract, NOT a new
topic, and NOT a modification to ZoneConfig's frozen schema -- it is an
in-process stand-in for the delivery mechanism that schema is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ZonePPERequirements:
    """Zone-id -> required PPE item list, with a global fallback.

    `required_ppe` values are expected to be drawn from the same keys
    WorkerEventPayload.ppe_status uses (see ppe_compliance_service.py) --
    this class does not itself constrain what those strings are, since the
    frozen WorkerEvent contract doesn't either (ppe_status is a generic
    `map<string, boolean>`, not a fixed enum -- see worker_event_v1.py).
    """

    per_zone: dict[str, list[str]] = field(default_factory=dict)
    default_required_ppe: list[str] = field(default_factory=lambda: ["helmet", "vest"])

    def required_for(self, zone_id: str) -> list[str]:
        return list(self.per_zone.get(zone_id, self.default_required_ppe))
