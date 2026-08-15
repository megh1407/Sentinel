"""
response_service.py

The seam between the pure domain layer (domain/emergency_evaluator.py,
domain/response_classifier.py, domain/action_planner.py) and the wire /
state world. This is where uuid4(), datetime.now(), ExplanationObject
construction, and ResponseTrackingRepository reads/writes all happen --
kept out of domain/ specifically so the decision logic stays testable
without any of this.

Idempotency and escalation policy (master prompt SS16, SS23):

  - Duplicate delivery of the SAME event_id (at-least-once Kafka delivery)
    is a no-op: ResponseTrackingRepository.was_event_processed/
    mark_event_processed dedupes on event_id specifically.

  - A NEW RiskScore event for the same risk_id is not automatically a
    duplicate -- SS23 is explicit that new evidence may legitimately cause
    escalation rather than being suppressed. This service compares the new
    ResponseSeverity against the active response's last-seen severity
    (ResponseTrackingRepository.get_active_response) and only suppresses
    re-emitting an IDENTICAL, unescalated response (same severity, same
    action-type set) within the active window -- any severity change
    (escalation OR, where policy permits, downgrade -- SS16) still
    produces fresh actions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.evidence_item import EvidenceItem
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.action_request_v1 import (
    ActionLifecycleState, ActionRequestPayload, ActionRequestV1, ActionPriority, ActionType, ActionUrgency,
)
from sentinel_contracts.events.action_result_v1 import ActionOutcome, ActionResultV1
from sentinel_contracts.events.risk_score_v1 import RiskScoreLevel, RiskScoreV1

from response_agent.domain.action_planner import plan_actions
from response_agent.domain.emergency_evaluator import PreviousRisk, evaluate_emergency
from response_agent.domain.enums import SEVERITY_RANK, ResponseSeverity
from response_agent.domain.response_classifier import classify_response
from response_agent.models.action_plan import ActionPlan

AGENT_NAME = "response_agent"
AGENT_VERSION = "0.1.0"

PREVIOUS_RISK_TTL_SECONDS = 3600
ACTIVE_RESPONSE_TTL_SECONDS = 86400
EVENT_DEDUPE_TTL_SECONDS = 86400
ACTION_META_TTL_SECONDS = 86400


class ResponseService:
    def __init__(self, response_repo=None, logger=None):
        """`response_repo`: ResponseTrackingRepository | None. None means no
        Redis backend is configured for this agent process -- every method
        below degrades to 'no idempotency / no velocity detection / no
        escalation memory', matching StateContainer's own fail-open design
        (see permit_intelligence_agent._is_duplicate's identical pattern),
        never a hard failure. `logger`: the agent's injected structlog-style
        logger (BaseAgent.logger), optional so this class stays constructible
        in a plain unit test with no container."""
        self._repo = response_repo
        self._logger = logger

    def _log(self, event: str, **kwargs) -> None:
        if self._logger is not None:
            self._logger.info(event, **kwargs)

    # -- RiskScore handling --
    def handle_risk_score(self, risk: RiskScoreV1) -> list[ActionRequestV1] | None:
        if self._repo is not None and self._repo.was_event_processed(str(risk.event_id)):
            self._log("duplicate RiskScore ignored", event_id=str(risk.event_id))
            return None

        previous = self._load_previous_risk(risk.zone_id) if risk.zone_id else None
        emergency = evaluate_emergency(risk, previous)
        severity = classify_response(risk.payload.risk_level, emergency)

        if self._is_unescalated_duplicate(risk.payload.risk_id, severity):
            self._log(
                "unchanged severity for an already-active response -- suppressing duplicate actions",
                risk_id=risk.payload.risk_id, severity=severity.value,
            )
            self._mark_processed(risk, risk.zone_id)
            return None

        plans = plan_actions(risk, emergency, severity)
        actions = [self._to_action_request(risk, plan, ActionLifecycleState.REQUESTED) for plan in plans]

        self._mark_processed(risk, risk.zone_id)
        self._update_active_response(risk.payload.risk_id, severity, plans)
        for action in actions:
            self._remember_action_meta(action, risk.payload.risk_id)
        return actions

    # -- ActionResult handling (SS13, SS16, SS22 test 6/9) --
    def handle_action_result(self, result: ActionResultV1) -> list[ActionRequestV1] | None:
        if self._repo is not None and self._repo.was_event_processed(str(result.event_id)):
            self._log("duplicate ActionResult ignored", event_id=str(result.event_id))
            return None
        if self._repo is not None:
            self._repo.mark_event_processed(str(result.event_id), ttl_seconds=EVENT_DEDUPE_TTL_SECONDS)

        if result.payload.outcome not in (ActionOutcome.FAILED, ActionOutcome.EXPIRED, ActionOutcome.REJECTED):
            return None  # APPROVED/EXECUTED needs no response-agent follow-up

        meta = self._repo.get_action_meta(str(result.payload.action_id)) if self._repo is not None else None
        if meta is None:
            # SS22: never silently ignore a failure -- but with no provenance
            # for this action_id (e.g. process restarted after the TTL
            # window, or the action predates this agent version), there is
            # nothing concrete to escalate. Log loudly and stop; do not
            # guess at a risk_id/zone to attach an escalation to.
            self._log(
                "action failed/rejected but no provenance found -- cannot escalate",
                action_id=str(result.payload.action_id), outcome=result.payload.outcome.value,
            )
            return None

        escalation_key = f"escalated:{result.payload.action_id}"
        if self._repo is not None and self._repo.was_event_processed(escalation_key):
            self._log("action already escalated once -- not re-escalating", action_id=str(result.payload.action_id))
            return None

        plan = ActionPlan(
            action_type=ActionType.REQUEST_HUMAN_REVIEW,
            target_ref=meta["zone_id"] or meta["risk_id"],
            urgency=ActionUrgency.IMMEDIATE, priority=ActionPriority.CRITICAL,
            reason=(
                f"Escalating: action {result.payload.action_id} ({meta['action_type']}) for risk "
                f"{meta['risk_id']} ended in {result.payload.outcome.value}"
                + (f" ({result.payload.failure_reason})" if result.payload.failure_reason else "") + "."
            ),
            requires_human_approval=True, acknowledgement_required=True,
            acknowledgement_deadline_seconds=5 * 60,
            emergency_triggered=meta.get("emergency_triggered", False),
        )
        action = self._to_action_request_for_risk(
            risk_id=meta["risk_id"], zone_id=meta["zone_id"], site_id=result.site_id,
            correlation_id=result.correlation_id, causation_id=result.event_id, plan=plan,
            lifecycle_state=ActionLifecycleState.ESCALATED,
        )
        if self._repo is not None:
            self._repo.mark_event_processed(escalation_key, ttl_seconds=EVENT_DEDUPE_TTL_SECONDS)
            self._remember_action_meta(action, meta["risk_id"])
        return [action]

    # -- previous-risk / velocity --
    def _load_previous_risk(self, zone_id: str) -> PreviousRisk | None:
        if self._repo is None:
            return None
        raw = self._repo.get_previous_risk(zone_id)
        if raw is None:
            return None
        return PreviousRisk(score=raw["score"], risk_level=RiskScoreLevel(raw["risk_level"]))

    def _mark_processed(self, risk: RiskScoreV1, zone_id: str | None) -> None:
        if self._repo is None:
            return
        self._repo.mark_event_processed(str(risk.event_id), ttl_seconds=EVENT_DEDUPE_TTL_SECONDS)
        if zone_id:
            self._repo.set_previous_risk(
                zone_id, score=risk.payload.score, risk_level=risk.payload.risk_level.value,
                observed_at=risk.event_timestamp.isoformat(), ttl_seconds=PREVIOUS_RISK_TTL_SECONDS,
            )

    # -- active-response dedupe/escalation memory --
    def _is_unescalated_duplicate(self, risk_id: str, severity: ResponseSeverity) -> bool:
        if self._repo is None:
            return False
        active = self._repo.get_active_response(risk_id)
        if active is None:
            return False
        return active.get("severity") == severity.value

    def _update_active_response(self, risk_id: str, severity: ResponseSeverity, plans: list[ActionPlan]) -> None:
        if self._repo is None:
            return
        if severity == ResponseSeverity.NORMAL:
            self._repo.clear_active_response(risk_id)
            return
        self._repo.set_active_response(
            risk_id,
            {
                "severity": severity.value,
                "severity_rank": SEVERITY_RANK[severity],
                "action_types": sorted({p.action_type.value for p in plans}),
            },
            ttl_seconds=ACTIVE_RESPONSE_TTL_SECONDS,
        )

    def _remember_action_meta(self, action: ActionRequestV1, risk_id: str) -> None:
        if self._repo is None:
            return
        self._repo.set_action_meta(
            action.payload.action_id,
            {
                "risk_id": risk_id, "zone_id": action.zone_id, "action_type": action.payload.action_type.value,
                "emergency_triggered": action.payload.emergency_triggered,
            },
            ttl_seconds=ACTION_META_TTL_SECONDS,
        )

    # -- wire conversion --
    def _to_action_request(self, risk: RiskScoreV1, plan: ActionPlan, lifecycle_state: ActionLifecycleState) -> ActionRequestV1:
        return self._to_action_request_for_risk(
            risk_id=risk.payload.risk_id, zone_id=risk.zone_id, site_id=risk.site_id,
            correlation_id=risk.correlation_id, causation_id=risk.event_id, plan=plan,
            lifecycle_state=lifecycle_state, source_evidence=[
                EvidenceItem(
                    source_event_id=str(risk.event_id), source_type="RiskScore",
                    description=f"Source risk score that triggered this action ({risk.payload.risk_level.value}, score {risk.payload.score:.0f}).",
                    weight=1.0, timestamp=risk.event_timestamp,
                ),
            ],
        )

    def _to_action_request_for_risk(
        self, *, risk_id: str, zone_id: str | None, site_id: str, correlation_id, causation_id, plan: ActionPlan,
        lifecycle_state: ActionLifecycleState, source_evidence: list[EvidenceItem] | None = None,
    ) -> ActionRequestV1:
        now = datetime.now(timezone.utc)
        action_id = f"ACT-{uuid.uuid4()}"
        ack_deadline = now + timedelta(seconds=plan.acknowledgement_deadline_seconds) if plan.acknowledgement_deadline_seconds else None
        deadline = now + timedelta(seconds=plan.deadline_seconds) if plan.deadline_seconds else None

        payload = ActionRequestPayload(
            action_id=action_id, risk_id=risk_id, action_type=plan.action_type, target_ref=plan.target_ref,
            requested_by=AGENT_NAME, urgency=plan.urgency, requires_human_approval=plan.requires_human_approval,
            requires_dual_control=plan.requires_dual_control, priority=plan.priority, lifecycle_state=lifecycle_state,
            emergency_triggered=plan.emergency_triggered, trigger_reason=plan.trigger_reason,
            acknowledgement_required=plan.acknowledgement_required, acknowledgement_deadline=ack_deadline,
            deadline=deadline,
        )
        explanation = ExplanationObject(
            summary=plan.reason,
            confidence=ConfidenceScore(value=0.9, derivation=ConfidenceDerivation.RULE_BASED,
                                        rule_id="response_agent_action_planner_v1", rule_version=1),
            evidence=source_evidence or [],
            reasoning_steps=[plan.reason],
            risk_contributors=[],
            generated_at=now,
        )
        return ActionRequestV1(
            event_id=uuid.uuid4(), event_timestamp=now, correlation_id=correlation_id, causation_id=causation_id,
            producer_service=AGENT_NAME, producer_version=AGENT_VERSION, site_id=site_id, zone_id=zone_id,
            partition_key=plan.target_ref, metadata=Metadata(schema_id=0, schema_version=1, environment=Environment.DEV),
            justification=explanation, payload=payload,
        )
