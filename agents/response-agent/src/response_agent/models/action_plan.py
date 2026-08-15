"""
action_plan.py

ActionPlan is the Response Agent's internal, in-process representation of
one planned action -- structurally, it is what master prompt SS8's
`ResponseAction` describes. It is deliberately NOT the wire contract:
services/response_service.py converts a list of these into real
ActionRequestV1 events (sentinel_contracts.events.action_request_v1),
attaching the event envelope, IDs, and ExplanationObject that only make
sense at publish time. Keeping this separate lets domain/action_planner.py
stay pure (no uuid4()/datetime.now() calls, no envelope fields) and
therefore trivially unit-testable -- see tests/unit/test_action_planner.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sentinel_contracts.events.action_request_v1 import ActionPriority, ActionType, ActionUrgency


@dataclass
class ActionPlan:
    action_type: ActionType
    target_ref: str
    urgency: ActionUrgency
    priority: ActionPriority
    reason: str
    requires_human_approval: bool = True
    requires_dual_control: bool = False
    acknowledgement_required: bool = False
    acknowledgement_deadline_seconds: int | None = None  # offset from event_timestamp, resolved at publish time
    deadline_seconds: int | None = None  # offset from event_timestamp
    emergency_triggered: bool = False
    trigger_reason: str | None = None
    evidence_source_ids: list[str] = field(default_factory=list)
