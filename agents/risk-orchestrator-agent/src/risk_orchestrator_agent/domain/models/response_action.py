"""Response-directive value objects.

Realizes the "Response Directive" branch of the expected output contract
(user-provided spec, §"output contract"): `recommended_response` +
`response_actions`. This is still the Orchestrator's output, not the
Response Agent's — these are *recommendations* the Response Agent
converts into actual dispatched actions (evacuate, suspend permit,
notify, shutdown). The Orchestrator names what should happen and why;
executing it is explicitly out of this agent's boundary (see the user's
own architectural-boundary diagram).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ResponseAction:
    action: str  # e.g. "EVACUATE", "RESTRICT_ACCESS", "SUSPEND_PERMIT", "ALERT_EMERGENCY_RESPONSE_TEAM"
    target: str  # a zone_id, permit_id, or "COMMAND_CENTER"
    priority: str  # "IMMEDIATE" | "URGENT" | "STANDARD"
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RecommendedResponse:
    response_type: str  # "EMERGENCY" | "ELEVATED" | "ROUTINE" | "NONE"
    priority: str  # "IMMEDIATE" | "URGENT" | "STANDARD" | "NONE"
    requires_human_confirmation: bool
    actions: tuple[ResponseAction, ...] = field(default_factory=tuple)
