"""Enumerations for event contracts, topics, and evidence provenance."""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """`event_type` discriminator values used across `domain/events`.

    Inbound types mirror Phase 1 §4's six analysis payloads; outbound and
    internal types mirror Phase 1 §5 and Phase 2.5 §6.2's domain-event
    catalog. Kept as one enum (not split inbound/outbound) so a single
    dispatch `match` statement (Coding Standards §2.6) can switch on it.
    """

    # Inbound (Intelligence Agent) analysis events
    WORKER_ANALYSIS = "worker.analysis.complete"
    ZONE_ANALYSIS = "zone.analysis.complete"
    PERMIT_ANALYSIS = "permit.analysis.complete"
    MAINTENANCE_ANALYSIS = "maintenance.analysis.complete"
    ENVIRONMENT_ANALYSIS = "environment.analysis.complete"
    INCIDENT_ANALYSIS = "incident.analysis.complete"

    # Outbound (Risk Orchestrator) events
    RISK_SCORE_COMPUTED = "risk.score.computed"
    SITE_STATE_CHANGED = "site.state_change"
    PREDICTION_CONTRIBUTED = "prediction.contributed"

    # Internal domain events (Phase 2.5 §6.2) — not independently published,
    # but named here so `domain/events` can model them explicitly.
    RISK_ASSESSMENT_CREATED = "risk_assessment.created"
    COMPOUND_RISK_IDENTIFIED = "compound_risk.identified"
    DECISION_CREATED = "decision.created"
    EMERGENCY_TRIGGERED = "emergency.triggered"
    RECOMMENDATION_GENERATED = "recommendation.generated"
    RISK_RESOLVED = "risk.resolved"
    DECISION_CLOSED = "decision.closed"
    ASSESSMENT_EXPIRED = "assessment.expired"


class ContextType(str, Enum):
    """Which domain sub-context a piece of data belongs to (Phase 2.2 §4.1)."""

    WORKER = "worker"
    ZONE = "zone"
    EQUIPMENT = "equipment"
    PERMIT = "permit"
    SENSOR = "sensor"
    INCIDENT = "incident"
    MAINTENANCE = "maintenance"
    HISTORICAL = "historical"
    NEIGHBOR_ZONE = "neighbor_zone"


class EvidenceType(str, Enum):
    """`EvidenceItem.evidence_type` values (Phase 2.2 §11.1)."""

    SENSOR_READING = "sensor_reading"
    AGENT_INFERENCE = "agent_inference"
    HISTORICAL_PRECEDENT = "historical_precedent"
    TOPOLOGY_FACT = "topology_fact"
    MANUAL_OVERRIDE = "manual_override"


class ConfidenceLevel(str, Enum):
    """A coarse, human-readable banding over a raw `ConfidenceScore`.

    Purely a display/reporting convenience — no domain logic ever branches
    on this in place of the underlying float (Phase 2.3 §10.4's confidence
    matrix uses these bands descriptively, not as the source of truth).
    """

    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class ConfidenceDerivationMethod(str, Enum):
    """How a `ConfidenceScore` was produced (CSEGS terminology)."""

    MODEL_BASED = "model_based"
    RULE_BASED = "rule_based"
    SENSOR_GROUNDED = "sensor_grounded"
    DERIVED = "derived"


class PredictionSource(str, Enum):
    """Which registered producer contributed a `sentinel.prediction.v1`
    event (Phase 1 §5.3)."""

    RISK_ORCHESTRATOR = "risk_orchestrator_agent"
    MAINTENANCE_INTELLIGENCE = "maintenance_intelligence_agent"
    ENVIRONMENTAL_INTELLIGENCE = "environmental_intelligence_agent"


class RecoveryMode(str, Enum):
    """The three-way failure-recovery classification used platform-wide
    (Phase 2.1 §10.2)."""

    DEGRADE_AND_CONTINUE = "degrade_and_continue"
    ISOLATE_AND_SKIP = "isolate_and_skip"
    FAIL_LOUD_AND_STOP = "fail_loud_and_stop"
