"""Concrete event contracts.

Inbound (Intelligence Agent) events, outbound (Risk Orchestrator)
events, and Phase 2.5 §6.2's internal domain-event catalog are all
represented as `DomainEvent` subclasses. Each subclass fixes its own
`event_type` default and adds the handful of top-level fields most
consumers need directly, while anything else rides in `payload` — this
mirrors the real wire contracts' "envelope + payload" split (Phase 1 §4)
without duplicating every payload field as a dataclass field.
"""

from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.domain.enums.event_types import EventType
from risk_orchestrator_agent.domain.events.base import DomainEvent

# --- Inbound: Intelligence Agent analysis events (Phase 1 §4) --------------


@dataclasses.dataclass(frozen=True, slots=True)
class WorkerStatusUpdated(DomainEvent):
    """`sentinel.worker.analysis.v1` (Phase 1 §4.1)."""

    event_type: EventType = EventType.WORKER_ANALYSIS
    zone_id: str = ""
    worker_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class ZoneIntelligenceUpdated(DomainEvent):
    """`sentinel.zone.analysis.v1` (Phase 1 §4.2)."""

    event_type: EventType = EventType.ZONE_ANALYSIS
    zone_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class PermitUpdated(DomainEvent):
    """`sentinel.permit.analysis.v1` (Phase 1 §4.3)."""

    event_type: EventType = EventType.PERMIT_ANALYSIS
    zone_id: str = ""
    permit_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class EquipmentRiskDetected(DomainEvent):
    """`sentinel.maintenance.analysis.v1` (Phase 1 §4.4)."""

    event_type: EventType = EventType.MAINTENANCE_ANALYSIS
    zone_id: str = ""
    equipment_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class EnvironmentUpdated(DomainEvent):
    """`sentinel.environment.analysis.v1` (Phase 1 §4.5)."""

    event_type: EventType = EventType.ENVIRONMENT_ANALYSIS
    zone_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class IncidentCreated(DomainEvent):
    """`sentinel.incident.analysis.v1` — new/updated incident precedent
    (Phase 1 §4.6)."""

    event_type: EventType = EventType.INCIDENT_ANALYSIS
    zone_id: str = ""
    incident_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class IncidentClosed(DomainEvent):
    """An incident's lifecycle reaching a closed state (Phase 2.5 §2)."""

    event_type: EventType = EventType.INCIDENT_ANALYSIS
    incident_id: str = ""


# --- Outbound: Risk Orchestrator events (Phase 1 §5) ------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class RiskAssessmentCreated(DomainEvent):
    """`sentinel.risk.score.v1` (Phase 1 §5.1, Phase 2.5 §6.2)."""

    event_type: EventType = EventType.RISK_SCORE_COMPUTED
    zone_id: str = ""
    assessment_id: str = ""
    score: int = 0
    severity: str = "negligible"


@dataclasses.dataclass(frozen=True, slots=True)
class CompoundRiskDetected(DomainEvent):
    """Internal domain event fired when `RuleEngine` produces a compound
    `RuleFinding` (Phase 2.3 §5, Phase 2.5 §6.2) — folds into
    `sentinel.risk.score.v1`'s `contributors[]` on publish, never its own
    topic (Phase 1 §5.1.1)."""

    event_type: EventType = EventType.COMPOUND_RISK_IDENTIFIED
    zone_id: str = ""
    factor_name: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class EmergencyTriggered(DomainEvent):
    """Internal domain event for a `Decision` reaching `EmergencyTier`
    (Phase 2.4 §6.1, Phase 2.5 §6.2) — realized on the wire as
    `severity in {critical, catastrophic}` + short `ttl_seconds` within
    `sentinel.risk.score.v1`, never a separate topic (Phase 2.4 §11.4)."""

    event_type: EventType = EventType.EMERGENCY_TRIGGERED
    zone_id: str = ""
    ttl_seconds: int = 15


@dataclasses.dataclass(frozen=True, slots=True)
class RecommendationGenerated(DomainEvent):
    """Internal domain event fired by `RecommendationCoordinator`
    (Phase 2.1 §3.9, Phase 2.5 §6.2)."""

    event_type: EventType = EventType.RECOMMENDATION_GENERATED
    zone_id: str = ""
    category: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class DecisionGenerated(DomainEvent):
    """Internal domain event for a `DecisionEngine` classification result
    (Phase 2.4 §2/§3, Phase 2.5 §6.2)."""

    event_type: EventType = EventType.DECISION_CREATED
    zone_id: str = ""
    decision_category: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class SiteStateChanged(DomainEvent):
    """`sentinel.site.state.v1` (Phase 1 §5.2)."""

    event_type: EventType = EventType.SITE_STATE_CHANGED
    site_id: str = ""
    overall_state: str = "normal"


@dataclasses.dataclass(frozen=True, slots=True)
class PredictionContributed(DomainEvent):
    """`sentinel.prediction.v1`, occasional/secondary (Phase 1 §5.3)."""

    event_type: EventType = EventType.PREDICTION_CONTRIBUTED
    zone_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class RiskResolved(DomainEvent):
    """Internal domain event for a `Decision` transitioning to `Resolved`
    (Phase 2.4 §6.6, Phase 2.5 §6.2) — evidence-driven, never time-decayed."""

    event_type: EventType = EventType.RISK_RESOLVED
    zone_id: str = ""
    decision_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class DecisionClosed(DomainEvent):
    """Internal domain event for a `Decision` reaching its terminal
    `Closed` state (Phase 2.5 §6.2)."""

    event_type: EventType = EventType.DECISION_CLOSED
    decision_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class AssessmentExpired(DomainEvent):
    """Internal domain event: a `RiskAssessment`'s `ttl_seconds` elapsed
    with no superseding assessment (Phase 2.5 §6.2). Not separately
    published — inferred by any consumer from `computed_at + ttl_seconds`
    already present in the original event."""

    event_type: EventType = EventType.ASSESSMENT_EXPIRED
    zone_id: str = ""
    assessment_id: str = ""
