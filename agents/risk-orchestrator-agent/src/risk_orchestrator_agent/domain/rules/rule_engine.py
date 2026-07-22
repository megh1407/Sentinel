"""domain/rules/rule_engine.py — RuleEngine.

Fills the gap `application/scoring_pipeline.py`'s own docstring names
explicitly: the fixed pipeline order is ContextBuilder -> CorrelationEngine
-> RuleEngine -> RiskScorer -> DecisionEngine -> ExplanationBuilder ->
EventPublisher, and only the first two stages existed before this file.

RuleEngine turns `RiskContext` facts plus `CorrelationFinding` evidence
into `RuleFinding`s: the first point in the pipeline where something is
judged relevant to risk, not just observed or related. It never computes
a score itself (that's RiskScorer) and never classifies severity (that's
DecisionEngine) — this stays a flat evaluation of independent rules, each
one small enough to unit-test and reason about alone, per the
"reconciled" architecture boundary in the master prompt (§17): Orchestrator
coordinates, Agent judges its own domain, RuleEngine/RiskScorer/
DecisionEngine judge the system.

Each `_RULE_*` function takes the `RiskContext` and the correlation
findings already attached to it, and returns zero or more `RuleFinding`s.
Deliberately a flat, explicit list rather than a config-driven rule table
(no `RuleSetLoadError`-worthy external rule-set format exists yet in this
codebase) — extending it means adding one function and registering it in
`_RULES`, per the additive-extension pattern already established by
`correlation_types.py`.
"""

from __future__ import annotations

import uuid

from risk_orchestrator_agent.domain.enums import CorrelationType, RuleCategory, RulePriority
from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding


def _new_id() -> str:
    return str(uuid.uuid4())


def _worker_ppe_violations(context: RiskContext) -> list[RuleFinding]:
    findings = []
    for worker in context.workers:
        if not worker.ppe_violations:
            continue
        findings.append(
            RuleFinding(
                rule_id="worker.ppe_violation",
                category=RuleCategory.WORKER_SAFETY,
                priority=RulePriority.HIGH,
                weight=0.5 + 0.1 * min(len(worker.ppe_violations), 3),
                confidence=worker.confidence.value,
                description=(
                    f"Worker {worker.worker_id} has PPE violations: "
                    f"{list(worker.ppe_violations)}"
                ),
                entity_refs=(worker.worker_id,),
            )
        )
    return findings


def _worker_proximity_alerts(context: RiskContext) -> list[RuleFinding]:
    findings = []
    for worker in context.workers:
        for alert in worker.proximity_alerts:
            if not alert.within_hazard_radius:
                continue
            findings.append(
                RuleFinding(
                    rule_id="worker.proximity_hazard",
                    category=RuleCategory.WORKER_SAFETY,
                    priority=RulePriority.CRITICAL,
                    weight=0.8,
                    confidence=worker.confidence.value,
                    description=(
                        f"Worker {worker.worker_id} is {alert.distance_m}m from "
                        f"{alert.hazard_type} (safe distance {alert.safe_distance_m}m)"
                    ),
                    entity_refs=(worker.worker_id,),
                )
            )
    return findings


def _equipment_faults(context: RiskContext) -> list[RuleFinding]:
    findings = []
    for eq in context.equipment:
        if not eq.active_faults:
            continue
        findings.append(
            RuleFinding(
                rule_id="equipment.active_fault",
                category=RuleCategory.EQUIPMENT,
                priority=RulePriority.HIGH,
                weight=0.4 + 0.15 * min(len(eq.active_faults), 3),
                confidence=eq.confidence.value,
                description=f"Equipment {eq.equipment_id} has active faults: {list(eq.active_faults)}",
                entity_refs=(eq.equipment_id,),
            )
        )
        if eq.failure_prediction is not None and eq.failure_prediction.probability >= 0.5:
            findings.append(
                RuleFinding(
                    rule_id="equipment.predicted_failure",
                    category=RuleCategory.EQUIPMENT,
                    priority=RulePriority.MEDIUM,
                    weight=eq.failure_prediction.probability * 0.6,
                    confidence=eq.confidence.value,
                    description=(
                        f"Equipment {eq.equipment_id} has a "
                        f"{eq.failure_prediction.probability:.0%} predicted failure "
                        f"probability within {eq.failure_prediction.predicted_window_h}h"
                    ),
                    entity_refs=(eq.equipment_id,),
                )
            )
    return findings


def _maintenance_overdue(context: RiskContext) -> list[RuleFinding]:
    findings = []
    for maint in context.maintenance:
        if not maint.overdue_tasks:
            continue
        findings.append(
            RuleFinding(
                rule_id="maintenance.overdue",
                category=RuleCategory.EQUIPMENT,
                priority=RulePriority.MEDIUM,
                weight=0.3 + 0.1 * min(len(maint.overdue_tasks), 3),
                confidence=maint.confidence.value,
                description=f"Equipment {maint.equipment_id} has overdue maintenance: {list(maint.overdue_tasks)}",
                entity_refs=(maint.equipment_id,),
            )
        )
    return findings


def _permit_conflicts(context: RiskContext) -> list[RuleFinding]:
    findings = []
    for permit in context.permits:
        if permit.conflicts:
            findings.append(
                RuleFinding(
                    rule_id="permit.conflict",
                    category=RuleCategory.PERMIT,
                    priority=RulePriority.HIGH,
                    weight=0.5,
                    confidence=permit.confidence.value,
                    description=(
                        f"Permit {permit.permit_id} conflicts with "
                        f"{[c.conflicting_permit_id for c in permit.conflicts]}"
                    ),
                    entity_refs=(permit.permit_id,),
                )
            )
        if permit.zone_compatibility is False:
            findings.append(
                RuleFinding(
                    rule_id="permit.zone_incompatible",
                    category=RuleCategory.PERMIT,
                    priority=RulePriority.HIGH,
                    weight=0.5,
                    confidence=permit.confidence.value,
                    description=f"Permit {permit.permit_id} is not compatible with the current zone state",
                    entity_refs=(permit.permit_id,),
                )
            )
    return findings


def _sensor_hazards(context: RiskContext) -> list[RuleFinding]:
    if context.sensor is None:
        return []
    findings = []
    for hazard in context.sensor.hazards:
        if not hazard.threshold_breach:
            continue
        weight = 0.7 if hazard.trend == "rising" else 0.5
        findings.append(
            RuleFinding(
                rule_id="sensor.hazard_threshold_breach",
                category=RuleCategory.ENVIRONMENTAL,
                priority=RulePriority.CRITICAL,
                weight=weight,
                confidence=context.sensor.confidence.value,
                description=(
                    f"{hazard.hazard_type} at {hazard.measured_value}{hazard.unit} "
                    f"exceeds threshold ({hazard.trend}) in zone {context.zone_id}"
                ),
                entity_refs=(context.zone_id,),
            )
        )
    if context.sensor.evacuation_required:
        findings.append(
            RuleFinding(
                rule_id="sensor.evacuation_required",
                category=RuleCategory.ENVIRONMENTAL,
                priority=RulePriority.CRITICAL,
                weight=0.9,
                confidence=context.sensor.confidence.value,
                description=f"Environmental sensors indicate evacuation is required in zone {context.zone_id}",
                entity_refs=(context.zone_id,),
            )
        )
    return findings


def _zone_state(context: RiskContext) -> list[RuleFinding]:
    if context.zone is None:
        return []
    weight_by_state = {
        "danger": 0.7,
        "evacuate": 0.9,
        "lockdown": 1.0,
        "warning": 0.4,
        "watch": 0.2,
    }
    weight = weight_by_state.get(context.zone.zone_state)
    if weight is None:
        return []
    return [
        RuleFinding(
            rule_id="zone.elevated_state",
            category=RuleCategory.ZONE,
            priority=RulePriority.HIGH,
            weight=weight,
            confidence=context.zone.confidence.value,
            description=f"Zone {context.zone_id} is in state '{context.zone.zone_state}'",
            entity_refs=(context.zone_id,),
        )
    ]


def _historical_escalation(context: RiskContext) -> list[RuleFinding]:
    if context.historical is None or not context.historical.recent_transitions:
        return []
    return [
        RuleFinding(
            rule_id="historical.recent_transitions",
            category=RuleCategory.HISTORICAL,
            priority=RulePriority.LOW,
            weight=0.2,
            confidence=0.7,
            description=(
                f"Zone {context.zone_id} has {len(context.historical.recent_transitions)} "
                "recent severity transitions on record"
            ),
            entity_refs=(context.zone_id,),
        )
    ]


# Order matters only for readability/debugging — RiskScorer treats every
# RuleFinding as an independent, unordered contribution.
_RULES = (
    _worker_ppe_violations,
    _worker_proximity_alerts,
    _equipment_faults,
    _maintenance_overdue,
    _permit_conflicts,
    _sensor_hazards,
    _zone_state,
    _historical_escalation,
)


class RuleEngine:
    """Stateless domain service — a pure function of `RiskContext`, same
    idempotency guarantee as `CorrelationEngine` (no I/O, no clock reads
    beyond what's already embedded in the context)."""

    def evaluate(self, context: RiskContext) -> tuple[RuleFinding, ...]:
        findings: list[RuleFinding] = []
        for rule in _RULES:
            findings.extend(rule(context))
        return tuple(findings)
