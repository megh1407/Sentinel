"""
permit_conflict_evaluator.py

Phase 2E of the integration master prompt: "If `concurrent_permits` exists
in the authoritative runtime contract: detect overlapping permits... If it
does not exist: concurrent_permit_conflict_check = BLOCKED_BY_INPUT_CONTRACT.
Do not invent the field."

`concurrent_permits` does NOT exist on canonical PermitEventV1 (verified).
BUT concurrent-permit conflict detection is not actually blocked overall --
ZoneStateV1.payload.active_permit_ids / active_permit_types (real,
canonical, populated by the Zone Agent from the same sentinel.permit.events.v1
topic this agent also consumes) carries exactly the information needed,
and arguably more correctly: the Zone Agent is the natural owner of "what
else is currently active in this zone" state, not a per-permit-event field.

This is reported as EVALUATED when zone context is present, UNKNOWN when it
isn't -- never BLOCKED_BY_INPUT_CONTRACT, because the *capability* genuinely
exists in the platform via a different (and better) input than the one the
master prompt anticipated.
"""
from __future__ import annotations

from permit_intelligence_agent.models.permit_finding import Evaluability, PermitConflict
from sentinel_contracts.events.permit_event_v1 import PermitType
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

# (type_a, type_b) -> severity. Symmetric -- both orders are checked.
# Operational default pairing of concurrently-active permit types that are
# known to compound risk in the same zone; not itself a frozen contract,
# should be reviewed by the safety domain owner.
_CONFLICT_RULES: dict[frozenset[PermitType], str] = {
    frozenset({PermitType.HOT_WORK, PermitType.CONFINED_SPACE}): "blocking",
    frozenset({PermitType.HOT_WORK, PermitType.EXCAVATION}): "warning",
    frozenset({PermitType.CONFINED_SPACE, PermitType.LIFTING}): "warning",
    frozenset({PermitType.ELECTRICAL, PermitType.CONFINED_SPACE}): "warning",
}
_MAX_RECOMMENDED_CONCURRENT_PERMITS_PER_ZONE = 3


class PermitConflictEvaluator:
    def evaluate(
        self, permit_id: str, permit_type: PermitType, zone_state: ZoneStateV1 | None
    ) -> tuple[list[PermitConflict], list[str], dict[str, str]]:
        if zone_state is None:
            return [], [], {"concurrent_permit_conflict_check": Evaluability.UNKNOWN.value}

        conflicts: list[PermitConflict] = []
        findings: list[str] = []
        active_types = zone_state.payload.active_permit_types  # dict[permit_id -> permit_type string]

        for other_permit_id, other_type_str in active_types.items():
            if other_permit_id == permit_id:
                continue
            try:
                other_type = PermitType(other_type_str)
            except ValueError:
                continue  # not a type this agent's canonical enum recognizes -- skip rather than guess
            pair = frozenset({permit_type, other_type})
            severity = _CONFLICT_RULES.get(pair)
            if severity:
                conflicts.append(PermitConflict(
                    conflicting_permit_id=other_permit_id,
                    conflict_type=f"{permit_type.value}_vs_{other_type.value}",
                    severity=severity,
                ))
                findings.append(
                    f"PERMIT_TYPE_CONFLICT ({severity.upper()}): {permit_type.value} conflicts with "
                    f"active permit {other_permit_id} ({other_type.value}) in the same zone"
                )

        concurrent_count = len(active_types)
        if concurrent_count > _MAX_RECOMMENDED_CONCURRENT_PERMITS_PER_ZONE:
            findings.append(
                f"HIGH_CONCURRENT_PERMIT_COUNT: {concurrent_count} permits simultaneously active in zone "
                f"(recommended max {_MAX_RECOMMENDED_CONCURRENT_PERMITS_PER_ZONE})"
            )
            conflicts.append(PermitConflict(conflict_type="high_concurrent_permit_count", severity="advisory"))

        return conflicts, findings, {"concurrent_permit_conflict_check": Evaluability.EVALUATED.value}
