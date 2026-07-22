"""
permit_condition_evaluator.py

Phase 2D of the integration master prompt: evaluate whatever conditions the
canonical PermitEventV1.payload.conditions list actually carries
(list[PermitConditionRef], each with an explicit `is_satisfied: bool`) --
never assume a condition holds just because it exists.

Phase 2E/2F: `concurrent_permits`, `gas_test_required`, `isolation_points`,
and `zone_restrictions` (all fields the friend's ZIP implemented) do not
exist anywhere on the canonical PermitEventV1 payload. This evaluator
reports that fact structurally (Evaluability.BLOCKED_BY_INPUT_CONTRACT /
NOT_EVALUABLE) rather than fabricating a value the input contract cannot
actually support. Concurrent-permit conflict detection is NOT blocked,
however -- it is available through ZoneStateV1.payload.active_permit_ids /
active_permit_types instead, which is architecturally the correct source
(the Zone Agent, not the permit's own event, is what tracks "what else is
active in this zone" -- see zone_compatibility_evaluator.py).
"""
from __future__ import annotations

from permit_intelligence_agent.models.permit_finding import Evaluability
from sentinel_contracts.events.permit_event_v1 import PermitEventPayload


class PermitConditionEvaluator:
    def evaluate(self, payload: PermitEventPayload) -> tuple[list[str], dict[str, str]]:
        findings: list[str] = []
        evaluability: dict[str, str] = {}

        if payload.conditions:
            unsatisfied = [c for c in payload.conditions if not c.is_satisfied]
            evaluability["permit_conditions"] = Evaluability.EVALUATED.value
            for c in unsatisfied:
                findings.append(f"CONDITION_UNSATISFIED: {c.condition_id} ({c.description})")
        else:
            # No conditions attached is a legitimate state (not every permit
            # type requires them) -- still explicitly EVALUATED, not skipped.
            evaluability["permit_conditions"] = Evaluability.EVALUATED.value

        # Fields that simply do not exist on the canonical input contract.
        # Not invented, not silently ignored -- explicitly reported blocked.
        evaluability["gas_test_requirement_check"] = Evaluability.NOT_EVALUABLE.value
        evaluability["isolation_point_check"] = Evaluability.BLOCKED_BY_INPUT_CONTRACT.value
        evaluability["explicit_zone_restriction_check"] = Evaluability.BLOCKED_BY_INPUT_CONTRACT.value

        return findings, evaluability

    @staticmethod
    def unsatisfied_ratio(payload: PermitEventPayload) -> float:
        if not payload.conditions:
            return 0.0
        unsatisfied = sum(1 for c in payload.conditions if not c.is_satisfied)
        return unsatisfied / len(payload.conditions)
