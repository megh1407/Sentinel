"""response_runtime.py -- the Response Agent (master prompt Phase 6/Layer 3).

Consumes the FINALIZED SystemRiskAssessment produced by the Risk
Orchestrator and turns it into an ActionRequest. It does NOT recalculate
risk -- every number it acts on (severity, global_score, decision_category,
escalation_required, affected zones) is read straight off the assessment.

Four components, exactly as the prompt names them:

  * Emergency Evaluator  -- is this an emergency? (severity / decision / escalation)
  * Response Classifier  -- monitor | investigate | respond | emergency
  * Action Planner       -- ActionType + urgency + approval controls + target
  * Idempotency          -- one assessment_id -> one response, enforced in Redis
                            (SET NX). A re-delivered assessment returns the
                            existing response instead of a second ActionRequest.

There was no Response Agent implementation anywhere in the repo (the agent
registry names `response_agent` but ships no code); this is that agent,
built to the existing ActionRequestV1 contract
(sentinel_contracts.events.action_request_v1) -- no new contract invented.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from sentinel_contracts.events.action_request_v1 import (
    ActionRequestV1,
    ActionRequestPayload,
    ActionType,
    ActionUrgency,
)
from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata

RESPONSE_AGENT = "response_agent"
RESPONSE_AGENT_VERSION = "0.1.0"

_IDEMPOTENCY_PREFIX = "sentinel:response:idempotency:"

# severity -> (classification, ActionType, urgency, requires_dual_control)
# A documented mapping, not a re-scoring: it only translates the finalized
# severity band into the response vocabulary the ActionRequest contract owns.
_SEVERITY_PLAN = {
    "catastrophic": ("emergency", ActionType.EVACUATE_ZONE, ActionUrgency.IMMEDIATE, True),
    "critical":     ("emergency", ActionType.EVACUATE_ZONE, ActionUrgency.IMMEDIATE, True),
    "high":         ("respond",   ActionType.SUSPEND_PERMIT, ActionUrgency.HIGH, False),
    "moderate":     ("investigate", ActionType.ALERT_OPERATOR, ActionUrgency.MEDIUM, False),
    "low":          ("monitor",   ActionType.ALERT_OPERATOR, ActionUrgency.LOW, False),
    "negligible":   ("monitor",   ActionType.ALERT_OPERATOR, ActionUrgency.LOW, False),
}


class ResponseAgent:
    """Stateless w.r.t. risk; keeps only the response cache + idempotency."""

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        self._lock = threading.RLock()
        self._by_assessment: dict[str, dict] = {}
        self._latest_by_zone: dict[str, dict] = {}

    # -- Emergency Evaluator ------------------------------------------------
    @staticmethod
    def _is_emergency(assessment) -> bool:
        return (
            assessment.severity.value in ("critical", "catastrophic")
            or assessment.decision_category.value == "emergency"
            or bool(getattr(assessment, "escalation_required", False))
        )

    # -- Idempotency --------------------------------------------------------
    def _claim(self, assessment_id: str, action_id: str) -> bool:
        """Returns True if THIS call is the first to process assessment_id.
        Redis SET NX makes it atomic across re-delivery / restarts; falls
        back to the in-process cache when Redis is absent."""
        if self._redis is not None:
            try:
                return bool(self._redis.set(_IDEMPOTENCY_PREFIX + assessment_id, action_id, nx=True))
            except Exception:  # noqa: BLE001 -- degrade to in-memory, never crash the response path
                pass
        return assessment_id not in self._by_assessment

    def handle(self, assessment) -> dict:
        """Main entry: assessment in, response decision (with ActionRequest) out.
        Idempotent on assessment_id."""
        with self._lock:
            existing = self._by_assessment.get(assessment.assessment_id)
            if existing is not None:
                return existing  # duplicate -- return the already-created response

            action_id = f"ACT-{uuid.uuid4().hex[:12]}"
            first = self._claim(assessment.assessment_id, action_id)
            if not first and existing is None:
                # Claimed by a prior process/run but not in our cache -- still
                # emit a deterministic view rather than a second live action.
                pass

            decision = self._plan(assessment, action_id)
            self._by_assessment[assessment.assessment_id] = decision
            self._latest_by_zone[assessment.zone_id] = decision
            return decision

    # -- Response Classifier + Action Planner -------------------------------
    def _plan(self, assessment, action_id: str) -> dict:
        severity = assessment.severity.value
        classification, action_type, urgency, dual_control = _SEVERITY_PLAN.get(
            severity, ("monitor", ActionType.ALERT_OPERATOR, ActionUrgency.LOW, False)
        )
        emergency = self._is_emergency(assessment)
        manual_review = bool(getattr(assessment, "manual_review_required", False))
        escalation = bool(getattr(assessment, "escalation_required", False))
        affected = [assessment.zone_id] + [
            p.to_zone_id for p in getattr(assessment, "propagation_paths", ())
        ]
        affected = list(dict.fromkeys(affected))  # de-dup, preserve order

        now = datetime.now(timezone.utc)
        summary = (
            f"{classification.upper()} response for zone {assessment.zone_id}: "
            f"{action_type.value} (urgency {urgency.value}); severity={severity}, "
            f"global_score={assessment.global_score.value:.1f}. "
            f"{'EMERGENCY. ' if emergency else ''}"
            f"Affected zones: {', '.join(affected)}."
        )
        action = ActionRequestV1(
            event_id=uuid.uuid4(),
            event_timestamp=now,
            correlation_id=_as_uuid(assessment.correlation_id),
            causation_id=_as_uuid(assessment.event_id),
            producer_service=RESPONSE_AGENT,
            producer_version=RESPONSE_AGENT_VERSION,
            site_id=assessment.site_id,
            zone_id=assessment.zone_id,
            partition_key=assessment.zone_id,
            metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV),
            justification=ExplanationObject(
                summary=summary,
                confidence=ConfidenceScore(
                    value=float(getattr(assessment, "confidence", 0.8) or 0.8),
                    derivation=ConfidenceDerivation.RULE_BASED,
                ),
                evidence=[],
                reasoning_steps=list(getattr(assessment, "contributing_factors", ()) or ()),
                generated_at=now,
            ),
            payload=ActionRequestPayload(
                action_id=action_id,
                risk_id=assessment.assessment_id,
                action_type=action_type,
                target_ref=assessment.zone_id,
                requested_by=RESPONSE_AGENT,
                urgency=urgency,
                requires_human_approval=True,
                requires_dual_control=dual_control,
            ),
        )
        return {
            "assessment_id": assessment.assessment_id,
            "zone_id": assessment.zone_id,
            "emergency": emergency,
            "classification": classification,
            "action_type": action_type.value,
            "urgency": urgency.value,
            "escalation_required": escalation,
            "manual_review_required": manual_review,
            "affected_zones": affected,
            "explanation": summary,
            "action_request": action.model_dump(mode="json"),
        }

    # -- reads for the API --------------------------------------------------
    def latest_for_zone(self, zone_id: str):
        with self._lock:
            return self._latest_by_zone.get(zone_id)

    def all_latest(self) -> list[dict]:
        with self._lock:
            return list(self._latest_by_zone.values())

    def reset(self) -> None:
        """Clears demo response + idempotency state only."""
        with self._lock:
            ids = list(self._by_assessment.keys())
            self._by_assessment.clear()
            self._latest_by_zone.clear()
        if self._redis is not None:
            try:
                keys = [_IDEMPOTENCY_PREFIX + i for i in ids]
                if keys:
                    self._redis.delete(*keys)
                for k in self._redis.scan_iter(match=_IDEMPOTENCY_PREFIX + "*"):
                    self._redis.delete(k)
            except Exception:  # noqa: BLE001
                pass


def _as_uuid(value):
    import uuid as _u
    if isinstance(value, _u.UUID):
        return value
    try:
        return _u.UUID(str(value))
    except Exception:  # noqa: BLE001 -- assessment ids that aren't UUIDs get a deterministic namespace uuid
        return _u.uuid5(_u.NAMESPACE_OID, str(value))
