"""
permit_analysis_builder.py

Assembles PermitFinding (the internal, pre-publish analysis result -- see
models/permit_finding.py for why it isn't yet a wire contract) from the
outputs of every evaluator, and derives confidence + recommendations.

Confidence deliberately drops below this agent's registered SLA
(min_confidence: 0.7, contracts/agent-registry/agents.yaml) when zone
context is unavailable -- an explicit, honest signal that this finding
needs review, rather than a fabricated high-confidence "safe" result.
Phase 3: "Never assume: No ZoneState = Safe" applies to confidence too,
not just to zone_compatibility.
"""
from __future__ import annotations

from datetime import datetime, timezone

from permit_intelligence_agent.models.permit_finding import PermitConflict, PermitFinding
from permit_intelligence_agent.services.permit_condition_evaluator import PermitConditionEvaluator
from permit_intelligence_agent.services.permit_conflict_evaluator import PermitConflictEvaluator
from permit_intelligence_agent.services.permit_lifecycle_validator import PermitLifecycleValidator
from permit_intelligence_agent.services.permit_risk_evaluator import PermitRiskEvaluator
from permit_intelligence_agent.services.zone_compatibility_evaluator import ZoneCompatibilityEvaluator
from sentinel_contracts.events.permit_event_v1 import PermitEventV1
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

_CONFIDENCE_WITH_ZONE_CONTEXT = 0.92
_CONFIDENCE_WITHOUT_ZONE_CONTEXT = 0.55  # deliberately below the agent's own 0.7 SLA floor


class PermitAnalysisBuilder:
    def __init__(self) -> None:
        self._lifecycle = PermitLifecycleValidator()
        self._conditions = PermitConditionEvaluator()
        self._zone_compat = ZoneCompatibilityEvaluator()
        self._conflicts = PermitConflictEvaluator()
        self._risk = PermitRiskEvaluator()

    def build(self, event: PermitEventV1, zone_state: ZoneStateV1 | None) -> PermitFinding:
        payload = event.payload
        findings: list[str] = []
        evaluability: dict[str, str] = {}

        lifecycle_valid, lifecycle_findings = self._lifecycle.evaluate(payload)
        findings += lifecycle_findings
        evaluability["permit_lifecycle_check"] = "EVALUATED"

        condition_findings, condition_evaluability = self._conditions.evaluate(payload)
        findings += condition_findings
        evaluability.update(condition_evaluability)
        unsatisfied_ratio = self._conditions.unsatisfied_ratio(payload)

        zone_compat, zone_risk, zone_findings, zone_evaluability = self._zone_compat.evaluate(
            payload.permit_type, zone_state
        )
        findings += zone_findings
        evaluability.update(zone_evaluability)

        conflicts, conflict_findings, conflict_evaluability = self._conflicts.evaluate(
            payload.permit_id, payload.permit_type, zone_state
        )
        findings += conflict_findings
        evaluability.update(conflict_evaluability)

        risk_score, risk_level = self._risk.calculate(
            lifecycle_valid=lifecycle_valid,
            zone_compatibility=zone_compat,
            zone_risk_at_issuance=zone_risk,
            conflicts=conflicts,
            unsatisfied_condition_ratio=unsatisfied_ratio,
        )

        confidence = _CONFIDENCE_WITH_ZONE_CONTEXT if zone_state is not None else _CONFIDENCE_WITHOUT_ZONE_CONTEXT

        evidence = [f"PermitEvent {event.event_id}"]
        if zone_state is not None:
            evidence.append(f"ZoneState {zone_state.event_id} (zone {zone_state.zone_id})")

        return PermitFinding(
            permit_id=payload.permit_id,
            permit_risk_level=risk_level,
            risk_score=risk_score,
            zone_compatibility=zone_compat,
            zone_risk_at_issuance=zone_risk,
            conflicts=conflicts,
            findings=findings,
            evaluability=evaluability,
            evidence=evidence,
            recommendations=self._recommendations(lifecycle_valid, zone_compat, conflicts, unsatisfied_ratio),
            confidence=confidence,
            analyzed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _recommendations(
        lifecycle_valid: bool, zone_compatibility: bool | None, conflicts: list[PermitConflict],
        unsatisfied_ratio: float,
    ) -> list[str]:
        recs: list[str] = []
        if not lifecycle_valid:
            recs.append("Do not authorize work under this permit until its lifecycle status/validity is corrected.")
        if zone_compatibility is False:
            recs.append("Suspend or defer this permit's work until zone conditions improve.")
        if zone_compatibility is None:
            recs.append("Zone context is unavailable -- treat as REQUIRES_REVIEW, not as cleared.")
        if any(c.severity == "blocking" for c in conflicts):
            recs.append("Resolve blocking permit conflicts in this zone before proceeding.")
        elif any(c.severity == "warning" for c in conflicts):
            recs.append("Review concurrent permits in this zone before proceeding.")
        if unsatisfied_ratio > 0:
            recs.append("Verify and satisfy all outstanding permit conditions before proceeding.")
        if not recs:
            recs.append("No corrective action required at this time.")
        return recs
