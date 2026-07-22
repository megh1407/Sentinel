"""Context entities — the per-domain sub-contexts and the `RiskContext`
aggregate root that composes them (Phase 2.2 §4, Phase 2.5 §3.1/§4.1).

Every sub-context here is a thin *reference* entity (Phase 2.5 §4.1):
this bounded context does not own a Worker's/Zone's/Equipment's/Permit's/
Incident's full lifecycle, only enough state to correlate against.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

from risk_orchestrator_agent.domain.entities.base import Entity
from risk_orchestrator_agent.domain.enums.status import (
    ContextLifecycleState,
    EquipmentStatus,
    IncidentSeverity,
    IncidentStatus,
    PermitRiskLevel,
    PermitStatus,
    WorkerSafetyStatus,
    ZoneState,
)
from risk_orchestrator_agent.shared.utilities.time_utils import utc_now


def _age_seconds(analyzed_at: datetime) -> float:
    """Wall-clock time since `analyzed_at` — the field every downstream
    staleness/expiration decision is computed from (Phase 2.2 §4.2).
    """
    return max(0.0, (utc_now() - analyzed_at).total_seconds())


@dataclasses.dataclass(eq=False)
class WorkerContext(Entity):
    """Point-in-time snapshot of a worker's safety state (Phase 1 §4.1,
    Phase 2.2 §4.1).
    """

    worker_id: str = ""
    safety_status: WorkerSafetyStatus = WorkerSafetyStatus.UNKNOWN
    ppe_compliance: float | None = None
    ppe_violations: tuple[str, ...] = ()
    zone_clearance: bool = False
    zone_id: str | None = None
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)
    confidence: float = 0.0

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class ZoneContext(Entity):
    """Point-in-time snapshot of a zone's operational state (Phase 1
    §4.2, Phase 2.2 §4.1)."""

    zone_id: str = ""
    site_id: str = ""
    zone_state: ZoneState = ZoneState.SAFE
    risk_score: int = 0
    confidence: float = 0.0
    risk_factors: tuple[str, ...] = ()
    worker_count: int = 0
    equipment_ids: tuple[str, ...] = ()
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class EquipmentContext(Entity):
    """Point-in-time snapshot of an equipment unit's health/fault state
    (Phase 1 §4.4, Phase 2.2 §4.1)."""

    equipment_id: str = ""
    zone_id: str | None = None
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    health_index: float = 1.0
    failure_probability: float | None = None
    failure_predicted_window_h: int | None = None
    #: Deliberately additive across updates (Phase 2.2 §3) — never
    #: overwritten by a newer update that happens to omit a fault still
    #: in effect, until an explicit resolution event is seen.
    active_faults: tuple[str, ...] = ()
    overdue_tasks: tuple[str, ...] = ()
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def with_additional_fault(self, fault: str) -> "EquipmentContext":
        """Return a copy with `fault` appended to `active_faults`,
        realizing Phase 2.2 §3's additive-merge rule without mutating
        the existing snapshot in place.
        """
        if fault in self.active_faults:
            return self
        return dataclasses.replace(self, active_faults=(*self.active_faults, fault))

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class PermitContext(Entity):
    """Point-in-time snapshot of a permit's scope/validity (Phase 1 §4.3,
    Phase 2.2 §4.1)."""

    permit_id: str = ""
    zone_id: str | None = None
    status: PermitStatus = PermitStatus.ACTIVE
    permit_risk_level: PermitRiskLevel = PermitRiskLevel.LOW
    conflicts: tuple[str, ...] = ()
    zone_compatibility: bool = True
    zone_risk_at_issuance: int | None = None
    equipment_ids: tuple[str, ...] = ()
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class EnvironmentContext(Entity):
    """Point-in-time snapshot of a zone's environmental/sensor state
    (Phase 1 §4.5). Realizes `SensorContext` from Phase 2.2 §4.1 — named
    `EnvironmentContext` here per the implementation brief's naming.
    """

    zone_id: str | None = None
    risk_score: int = 0
    confidence: float = 0.0
    evacuation_required: bool = False
    affected_zones: tuple[str, ...] = ()
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class IncidentContext(Entity):
    """Historical/active incident precedent, already resolved upstream by
    Incident Intelligence Agent (Phase 1 §4.6, Phase 2.2 §4.1)."""

    incident_id: str = ""
    severity: IncidentSeverity = IncidentSeverity.LOW
    status: IncidentStatus = IncidentStatus.CLOSED
    similarity: float | None = None
    incident_type: str | None = None
    occurred_at: datetime | None = None
    outcome: str | None = None
    root_cause: str | None = None
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class MaintenanceContext(Entity):
    """Overdue-task/fault-focused view of an equipment unit's
    maintenance state (Phase 2.2 §4.1) — distinct from `EquipmentContext`
    to preserve the composed-not-flattened model (Phase 2.2 §4.3)."""

    equipment_id: str = ""
    health_index: float = 1.0
    overdue_tasks: tuple[str, ...] = ()
    analyzed_at: datetime = dataclasses.field(default_factory=utc_now)

    def age_seconds(self) -> float:
        return _age_seconds(self.analyzed_at)


@dataclasses.dataclass(eq=False)
class HistoricalContext(Entity):
    """A zone's own recent severity trajectory (Phase 2.2 §4.1)."""

    zone_id: str = ""
    previous_severity: str | None = None
    previous_computed_at: datetime | None = None
    recent_transitions: tuple[str, ...] = ()


@dataclasses.dataclass(eq=False)
class NeighborZoneContext(Entity):
    """A neighboring zone's current state and relationship type
    (Phase 2.2 §4.1, §10)."""

    neighbor_zone_id: str = ""
    neighbor_state: ZoneState = ZoneState.SAFE
    distance_m: float = 0.0
    relationship_type: str = "adjacent"


@dataclasses.dataclass(eq=False)
class CorrelationContext(Entity):
    """The cycle-scoped, time-aligned graph of active entities produced
    by `CorrelationEngine`'s early workflow steps (Phase 2.3 §6.1's
    "Build Correlation Graph" step) — an internal working structure, not
    a Neo4j write.
    """

    zone_id: str = ""
    active_worker_ids: tuple[str, ...] = ()
    active_equipment_ids: tuple[str, ...] = ()
    active_permit_ids: tuple[str, ...] = ()
    time_window_seconds: int = 300


@dataclasses.dataclass(eq=False)
class RiskContext(Entity):
    """The aggregate root `ContextBuilder` assembles and hands downstream
    (Phase 2.2 §4.1, Phase 2.5 §3.1). A read-only, immutable-in-spirit
    snapshot for the duration of one scoring cycle — enforced by
    convention (only `ContextBuilder` may construct/mutate it, FRS §4.1),
    not by dataclass immutability, since Redis-backed rolling state must
    still be merged into it cycle over cycle before it is snapshotted.
    """

    zone_id: str = ""
    site_id: str = ""
    snapshot_at: datetime = dataclasses.field(default_factory=utc_now)
    lifecycle_state: ContextLifecycleState = ContextLifecycleState.CREATED

    worker_contexts: tuple[WorkerContext, ...] = ()
    zone_context: ZoneContext | None = None
    equipment_contexts: tuple[EquipmentContext, ...] = ()
    permit_contexts: tuple[PermitContext, ...] = ()
    environment_context: EnvironmentContext | None = None
    incident_context: IncidentContext | None = None
    maintenance_contexts: tuple[MaintenanceContext, ...] = ()
    historical_context: HistoricalContext | None = None
    neighbor_zone_contexts: tuple[NeighborZoneContext, ...] = ()

    #: Domains with no current data for this zone (Phase 2.2 §4.2's
    #: ContextQuality.missing_domains) — explicit, never silently omitted.
    missing_domains: tuple[str, ...] = ()
    stale_domains: tuple[str, ...] = ()
    completeness: float = 1.0
    context_builder_version: str = "1.0.0"

    def is_domain_present(self, domain: str) -> bool:
        return domain not in self.missing_domains

    def snapshot(self) -> "RiskContext":
        """Produce an immutable-in-spirit frozen copy for handoff to
        `CorrelationEngine` (Phase 2.2 §5.4). Implemented as a deep copy
        with `lifecycle_state` flipped to `SNAPSHOTTED` — callers are
        expected to treat the result as read-only from this point on.
        """
        frozen = self.deep_copy()
        frozen.lifecycle_state = ContextLifecycleState.SNAPSHOTTED
        frozen.snapshot_at = utc_now()
        return frozen
