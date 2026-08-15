"""
action_planner.py

Turns (RiskScoreV1, EmergencyDecision, ResponseSeverity) into a list of
ActionPlan objects (master prompt SS7-SS18). Pure function, no I/O -- see
models/action_plan.py for why the output type is deliberately not the
wire ActionRequestV1.

Design choices worth being explicit about (so a reviewer isn't left
guessing which master prompt section a given line implements):

  - SS9 ("avoid overreacting to isolated, controlled conditions"): ADVISORY
    severity produces exactly one low-urgency, no-approval-needed
    INCREASE_MONITORING action -- never zero actions. Master prompt SS20
    requires every significant response to be explainable, and this
    agent's only wire output IS an ActionRequest (there is no separate
    "no action taken, here is why" event type in the real contract -- see
    README's PLATFORM_GAP note) -- so "no response" would mean "no
    evidence this RiskScore was ever looked at", which the domain invariant
    against silent handling (master prompt SS22: "never silently ignore")
    rules out.

  - SS17 (cross-zone response): one action per affected zone, not one
    global action, when propagation_paths/affected_zones say more than one
    zone is implicated. The zone this RiskScore's own zone_id names always
    gets the most severe action; zones reached only via propagation get a
    lighter one, matching SS17's own worked example (ISOLATE vs
    RESTRICT_ACCESS vs INCREASE_MONITORING by distance from the source).

  - SS18 (cascade interruption point): the action targets the FIRST node
    in a cascade_paths chain (the earliest point in the chain), not the
    final zone the chain terminates at -- SS18 is explicit that response
    "should not only react to the final consequence."

  - SS12 step ordering (trigger protocol, notify, escalate, acknowledge,
    monitor) is expressed here as a flat list of ActionPlans rather than a
    literal 10-step sequence object, because every consumer of ActionRequest
    (Action Policy Gateway) already treats each ActionRequest as an
    independent, self-contained unit (Domain Invariant: "every Action
    references exactly one RiskScore") -- there is no wire concept of an
    ordered plan-of-plans to preserve, only the correctly-populated
    priority/urgency/acknowledgement fields on each independent action.
"""
from __future__ import annotations

from sentinel_contracts.events.action_request_v1 import ActionPriority, ActionType, ActionUrgency
from sentinel_contracts.events.risk_score_v1 import RiskScoreV1

from response_agent.domain.emergency_evaluator import EmergencyDecision
from response_agent.domain.enums import ResponseSeverity
from response_agent.models.action_plan import ActionPlan

# Acknowledgement/deadline windows, in seconds. Kept as named module
# constants (not hardcoded inline) so tests and future policy config can
# reference/override them by name rather than by magic number.
EMERGENCY_ACK_WINDOW_SECONDS = 5 * 60
CRITICAL_ACK_WINDOW_SECONDS = 15 * 60
EMERGENCY_ACTION_DEADLINE_SECONDS = 2 * 60
HIGH_PRIORITY_DEADLINE_SECONDS = 30 * 60


def plan_actions(risk: RiskScoreV1, emergency: EmergencyDecision, severity: ResponseSeverity) -> list[ActionPlan]:
    payload = risk.payload
    primary_zone = risk.zone_id or payload.risk_id  # site-wide aggregate scores (zone_id is None) target by risk_id
    reason = _reason_for(payload.risk_id, severity, emergency)

    if severity == ResponseSeverity.EMERGENCY:
        return _plan_emergency(primary_zone, payload, emergency, reason)
    if severity == ResponseSeverity.CRITICAL:
        return _plan_critical(primary_zone, reason)
    if severity == ResponseSeverity.HIGH_PRIORITY:
        return _plan_high_priority(primary_zone, reason)
    if severity == ResponseSeverity.WARNING:
        return _plan_warning(primary_zone, reason)
    # ADVISORY (and the currently-unreachable NORMAL) -- SS9/SS20, see module docstring.
    return _plan_advisory(primary_zone, reason)


def _reason_for(risk_id: str, severity: ResponseSeverity, emergency: EmergencyDecision) -> str:
    if emergency.emergency_triggered:
        return f"Risk {risk_id}: EMERGENCY -- {emergency.trigger_reason}"
    return f"Risk {risk_id}: {severity.value} response."


def _plan_emergency(primary_zone: str, payload, emergency: EmergencyDecision, reason: str) -> list[ActionPlan]:
    plans: list[ActionPlan] = [
        # Primary zone: the most severe action (SS17).
        ActionPlan(
            action_type=ActionType.ISOLATE_ZONE, target_ref=primary_zone,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS,
            deadline_seconds=EMERGENCY_ACTION_DEADLINE_SECONDS,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ),
        ActionPlan(
            action_type=ActionType.ALERT_OPERATOR, target_ref=primary_zone,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=False, acknowledgement_required=True,
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ),
        ActionPlan(
            action_type=ActionType.DISPATCH_RESPONSE_TEAM, target_ref=primary_zone,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ),
        ActionPlan(
            action_type=ActionType.CREATE_INCIDENT, target_ref=primary_zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=False, emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ),
    ]

    # SS17: zones reached only via propagation get a lighter action than
    # the primary zone, scaled by distance -- the immediate next hop
    # (RESTRICT_ACCESS) vs. further/preventive zones (INCREASE_MONITORING).
    propagation_targets = _propagation_targets(payload.propagation_paths, exclude=primary_zone)
    for i, zone in enumerate(propagation_targets):
        action_type = ActionType.RESTRICT_ACCESS if i == 0 else ActionType.INCREASE_MONITORING
        plans.append(ActionPlan(
            action_type=action_type, target_ref=zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.HIGH, reason=reason,
            requires_human_approval=(action_type == ActionType.RESTRICT_ACCESS),
            acknowledgement_required=(action_type == ActionType.RESTRICT_ACCESS),
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS if action_type == ActionType.RESTRICT_ACCESS else None,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ))
    # Any affected_zones not already covered by an explicit propagation
    # edge still get at least monitoring (SS4.C: never evaluate a zone in
    # isolation once it's implicated).
    covered = {primary_zone, *propagation_targets}
    for zone in payload.affected_zones:
        if zone not in covered:
            plans.append(ActionPlan(
                action_type=ActionType.INCREASE_MONITORING, target_ref=zone,
                urgency=ActionUrgency.HIGH, priority=ActionPriority.HIGH, reason=reason,
                requires_human_approval=False, emergency_triggered=True, trigger_reason=emergency.trigger_reason,
            ))
            covered.add(zone)

    # SS18: interrupt the cascade at its EARLIEST node, not its terminal zone.
    for chain in payload.cascade_paths:
        nodes = [n.strip() for n in chain.split("->") if n.strip()]
        if not nodes:
            continue
        earliest = nodes[0]
        if earliest in covered:
            continue
        plans.append(ActionPlan(
            action_type=ActionType.SHUTDOWN_REQUEST, target_ref=earliest,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL,
            reason=f"{reason} Earliest interruption point in cascade: {chain}.",
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS,
            deadline_seconds=EMERGENCY_ACTION_DEADLINE_SECONDS,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ))
        covered.add(earliest)

    # SS4.F: a confirmed critical-control failure alongside an emergency
    # always forces a human review action -- automation cannot be trusted
    # to compensate for a failed control on its own (SS19).
    if payload.critical_controls_unavailable:
        plans.append(ActionPlan(
            action_type=ActionType.REQUEST_HUMAN_REVIEW, target_ref=primary_zone,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL,
            reason=f"{reason} Critical control(s) unavailable: {', '.join(payload.critical_controls_unavailable)}.",
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=EMERGENCY_ACK_WINDOW_SECONDS,
            emergency_triggered=True, trigger_reason=emergency.trigger_reason,
        ))

    return plans


def _plan_critical(primary_zone: str, reason: str) -> list[ActionPlan]:
    """SS11: notify authority, restrict/stop, isolate if policy requires,
    human acknowledgement, continuous monitoring, incident record."""
    return [
        ActionPlan(
            action_type=ActionType.ALERT_OPERATOR, target_ref=primary_zone,
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=False, acknowledgement_required=True,
            acknowledgement_deadline_seconds=CRITICAL_ACK_WINDOW_SECONDS,
        ),
        ActionPlan(
            action_type=ActionType.RESTRICT_ACCESS, target_ref=primary_zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.CRITICAL, reason=reason,
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=CRITICAL_ACK_WINDOW_SECONDS,
        ),
        ActionPlan(
            action_type=ActionType.CREATE_INCIDENT, target_ref=primary_zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.HIGH, reason=reason,
            requires_human_approval=False,
        ),
        ActionPlan(
            action_type=ActionType.INCREASE_MONITORING, target_ref=primary_zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.HIGH, reason=reason,
            requires_human_approval=False,
        ),
    ]


def _plan_high_priority(primary_zone: str, reason: str) -> list[ActionPlan]:
    """SS10: notify operator, corrective action, increase monitoring,
    acknowledgement deadline, escalate-if-unacknowledged (the escalation
    itself is handled by services/response_service.py reacting to a future
    ActionResult/timeout, not planned here as a second action up front)."""
    return [
        ActionPlan(
            action_type=ActionType.ALERT_OPERATOR, target_ref=primary_zone,
            urgency=ActionUrgency.HIGH, priority=ActionPriority.HIGH, reason=reason,
            requires_human_approval=False, acknowledgement_required=True,
            acknowledgement_deadline_seconds=CRITICAL_ACK_WINDOW_SECONDS,
            deadline_seconds=HIGH_PRIORITY_DEADLINE_SECONDS,
        ),
        ActionPlan(
            action_type=ActionType.INCREASE_MONITORING, target_ref=primary_zone,
            urgency=ActionUrgency.MEDIUM, priority=ActionPriority.HIGH, reason=reason,
            requires_human_approval=False,
        ),
    ]


def _plan_warning(primary_zone: str, reason: str) -> list[ActionPlan]:
    """SS9: corrective action + monitoring + follow-up, no acknowledgement
    gate -- this is deliberately lighter-weight than HIGH_PRIORITY."""
    return [
        ActionPlan(
            action_type=ActionType.ALERT_OPERATOR, target_ref=primary_zone,
            urgency=ActionUrgency.MEDIUM, priority=ActionPriority.MEDIUM, reason=reason,
            requires_human_approval=False,
        ),
        ActionPlan(
            action_type=ActionType.INCREASE_MONITORING, target_ref=primary_zone,
            urgency=ActionUrgency.LOW, priority=ActionPriority.MEDIUM, reason=reason,
            requires_human_approval=False,
        ),
    ]


def _plan_advisory(primary_zone: str, reason: str) -> list[ActionPlan]:
    """SS9/SS20 -- see module docstring for why this is never empty."""
    return [
        ActionPlan(
            action_type=ActionType.INCREASE_MONITORING, target_ref=primary_zone,
            urgency=ActionUrgency.LOW, priority=ActionPriority.LOW, reason=reason,
            requires_human_approval=False,
        ),
    ]


def _propagation_targets(propagation_paths: list[str], exclude: str) -> list[str]:
    """Parses 'from_zone->to_zone' edges (RiskScorePayload.propagation_paths'
    documented format) into an ordered, deduplicated list of destination
    zones, nearest-first, excluding the primary zone itself."""
    targets: list[str] = []
    for edge in propagation_paths:
        parts = [p.strip() for p in edge.split("->") if p.strip()]
        if len(parts) < 2:
            continue
        for zone in parts[1:]:
            if zone != exclude and zone not in targets:
                targets.append(zone)
    return targets
