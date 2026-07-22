"""Status and lifecycle-state enumerations.

Covers per-domain reference-entity status vocabularies (Phase 2.5 §4.1) and
the aggregate lifecycle states from Phase 2.5 §3/§10. Kept separate from
`risk.py` because these describe *state*, not risk classification.
"""

from __future__ import annotations

from enum import Enum


class WorkerSafetyStatus(str, Enum):
    """`WorkerContext.safety_status` values (Phase 1 §4.1)."""

    SAFE = "safe"
    AT_RISK = "at_risk"
    UNKNOWN = "unknown"


class ZoneState(str, Enum):
    """`ZoneContext.zone_state` values (Phase 1 §4.2)."""

    SAFE = "safe"
    WATCH = "watch"
    WARNING = "warning"
    DANGER = "danger"
    EVACUATE = "evacuate"
    LOCKDOWN = "lockdown"


class SiteOverallState(str, Enum):
    """`SiteState.overall_state` values (Phase 1 §5.2)."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    WARNING = "warning"
    DANGER = "danger"
    LOCKDOWN = "lockdown"


class PermitStatus(str, Enum):
    """Lifecycle status of a permit reference entity."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CLOSED = "closed"


class PermitRiskLevel(str, Enum):
    """`PermitContext.permit_risk_level` values (Phase 1 §4.3)."""

    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"


class EquipmentStatus(str, Enum):
    """Equipment reference-entity operational status."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    FAULTED = "faulted"
    OFFLINE = "offline"
    UNDER_MAINTENANCE = "under_maintenance"


class IncidentSeverity(str, Enum):
    """Severity of a historical/active incident (Phase 1 §4.6)."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident reference entity."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ContextLifecycleState(str, Enum):
    """`OperationalContext` lifecycle states (Phase 2.5 §10.1, Phase 2.2 §5.1)."""

    CREATED = "created"
    UPDATING = "updating"
    REFRESHED = "refreshed"
    SNAPSHOTTED = "snapshotted"
    EXPIRING = "expiring"
    RECOVERING = "recovering"
    DESTROYED = "destroyed"


class RiskAssessmentStatus(str, Enum):
    """`RiskAssessment` externally-observed lifecycle (Phase 2.5 §10.2)."""

    CREATED = "created"
    CURRENT = "current"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class DecisionState(str, Enum):
    """`Decision` aggregate lifecycle states (Phase 2.4 §8.1, Phase 2.5 §10.3)."""

    PENDING = "pending"
    UNDER_EVALUATION = "under_evaluation"
    DECISION_CREATED = "decision_created"
    EMERGENCY_TIER = "emergency_tier"
    RECOMMENDATION_FLAGGED = "recommendation_flagged"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ContextQualityFlag(str, Enum):
    """Flags a domain contribution can carry (Phase 2.2 §12.3)."""

    PRESENT = "present"
    STALE = "stale"
    ABSENT = "absent"
    CONTESTED = "contested"
    UNKNOWN = "unknown"
    PARTIAL_EVIDENCE = "partial_evidence"
