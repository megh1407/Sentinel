"""domain/models/risk_decision_package.py — RiskDecisionPackage.

Matches the output contract the user specified directly: `decision_id`,
`risk_assessment`, `zone_risks`, `interaction_risks`, `permit_risks`,
`incident_context`, `risk_breakdown`, `risk_reasoning`,
`emergency_decision`, `recommended_response`, `response_actions`,
`provenance`. This is what `SiteOrchestrator` (application/
site_orchestration.py) produces and what `EventPublisher` publishes for
a site-level decision cycle — a level up from the single-zone
`SystemRiskAssessment` in `system_risk_assessment.py`, which stays
exactly as it was and is what this package's `zone_risks` are built
from.

Two fields in the source spec are **not backed by real modeled data**
in this codebase, and are populated conservatively rather than
fabricated — see `domain/decision/site_synthesizer.py`'s docstring for
specifics: `permit_risks[].permit_type` (no `PermitContext.permit_type`
field exists) and `incident_context.active_incidents` (`IncidentContext`
only models vector-similarity *historical* incidents, not currently
active ones).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum


def _json_safe(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


@dataclass(frozen=True, slots=True)
class RiskAssessmentSummary:
    overall_risk_level: str
    overall_risk_score: float
    confidence: float
    risk_scope: str  # "LOCALIZED" | "MULTI_ZONE" | "SYSTEMIC"
    affected_zones: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ZoneRiskSummary:
    zone_id: str
    risk_score: float
    risk_level: str
    risk_factors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InteractionRiskEntry:
    type: str  # e.g. "CROSS_ZONE_ESCALATION"
    zones: tuple[str, ...]
    severity: str
    reason: str


@dataclass(frozen=True, slots=True)
class PermitRiskEntry:
    permit_id: str
    permit_type: str | None  # see module docstring — not modeled upstream, may be None
    status: str  # "CONFLICTING" | "ZONE_INCOMPATIBLE"
    risk_contribution: str  # RulePriority-derived label
    reason: str


@dataclass(frozen=True, slots=True)
class IncidentContextSummary:
    active_incidents: tuple[str, ...]  # see module docstring — always empty today, not modeled upstream
    emergency_detected: bool
    emergency_type: str | None


@dataclass(frozen=True, slots=True)
class RiskBreakdown:
    local_risk: float
    cross_zone_risk: float
    permit_conflict_risk: float
    environmental_risk: float
    human_exposure_risk: float
    systemic_risk: float


@dataclass(frozen=True, slots=True)
class EmergencyDecision:
    is_emergency: bool
    triggered_by: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Provenance:
    source_agents: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskDecisionPackage:
    decision_id: str
    timestamp: datetime

    risk_assessment: RiskAssessmentSummary
    zone_risks: tuple[ZoneRiskSummary, ...]
    interaction_risks: tuple[InteractionRiskEntry, ...]
    permit_risks: tuple[PermitRiskEntry, ...]
    incident_context: IncidentContextSummary
    risk_breakdown: RiskBreakdown
    risk_reasoning: tuple[str, ...]
    emergency_decision: EmergencyDecision

    # `recommended_response`/`response_actions` are split in the spec's
    # JSON example (a summary object plus a flat action list); kept as
    # two attributes here for the same reason, with `to_dict()` emitting
    # them as separate top-level keys to match the example exactly.
    response_type: str
    response_priority: str
    requires_human_confirmation: bool
    response_actions: tuple  # tuple[ResponseAction, ...] — see response_action.py

    provenance: Provenance

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "risk_assessment": _json_safe(asdict(self.risk_assessment)),
            "zone_risks": _json_safe([asdict(z) for z in self.zone_risks]),
            "interaction_risks": _json_safe([asdict(i) for i in self.interaction_risks]),
            "permit_risks": _json_safe([asdict(p) for p in self.permit_risks]),
            "incident_context": _json_safe(asdict(self.incident_context)),
            "risk_breakdown": _json_safe(asdict(self.risk_breakdown)),
            "risk_reasoning": list(self.risk_reasoning),
            "emergency_decision": _json_safe(asdict(self.emergency_decision)),
            "recommended_response": {
                "response_type": self.response_type,
                "priority": self.response_priority,
                "requires_human_confirmation": self.requires_human_confirmation,
            },
            "response_actions": _json_safe([asdict(a) for a in self.response_actions]),
            "provenance": _json_safe(asdict(self.provenance)),
        }
