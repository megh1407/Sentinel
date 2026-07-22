"""RiskContext — the sole Aggregate Root realizing `OperationalContext`
(Phase 2.5 §3.1) for this bounded context's assembled, cross-domain view
of one zone.

Constructed and mutated only by ContextBuilder (Phase 2.5 §3.1's
ownership rule); every sub-context is reachable only through this
object, never referenced independently (Phase 2.2 §4.3's "composed, not
flattened" rationale).

The metadata value objects nested in Phase 2.2 §4.1's class diagram
(SiteContext, ConfidenceModel, VersionMetadata, CorrelationMetadata,
ContextQuality) are defined here, alongside their aggregate root, since
Phase 3.1 §2's file tree does not list them as independent files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import ConfidenceScore
from risk_orchestrator_agent.domain.models.correlation_finding import CorrelationFinding
from risk_orchestrator_agent.domain.models.equipment_context import EquipmentContext
from risk_orchestrator_agent.domain.models.evidence_collection import EvidenceCollection
from risk_orchestrator_agent.domain.models.historical_context import HistoricalContext
from risk_orchestrator_agent.domain.models.incident_context import IncidentContext
from risk_orchestrator_agent.domain.models.maintenance_context import MaintenanceContext
from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext
from risk_orchestrator_agent.domain.models.operational_timeline import OperationalTimeline
from risk_orchestrator_agent.domain.models.permit_context import PermitContext
from risk_orchestrator_agent.domain.models.sensor_context import SensorContext
from risk_orchestrator_agent.domain.models.worker_context import WorkerContext
from risk_orchestrator_agent.domain.models.zone_context import ZoneContext


@dataclass(frozen=True, slots=True)
class SiteContext:
    site_id: str
    overall_state: str = "normal"
    total_workers: int = 0
    active_permits: int = 0
    active_zone_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ConfidenceModel:
    """Preserves each domain's own reported confidence — ContextBuilder
    never overwrites a domain's self-reported confidence, only
    aggregates it (Phase 2.2 §4.2)."""

    aggregate_confidence: float
    per_domain_confidence: dict[str, float] = field(default_factory=dict)
    derivation_method: str = "completeness_weighted"


@dataclass(frozen=True, slots=True)
class VersionMetadata:
    context_builder_version: str
    schema_version: str = "v1"


@dataclass(frozen=True, slots=True)
class CorrelationMetadata:
    correlation_id: str
    causation_id: str | None
    input_event_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ContextQuality:
    """The single most safety-critical structure in this model (Phase
    2.2 §12.3) — the absence of a fact is never represented as the
    presence of safety."""

    completeness: float
    consistency: float = 1.0
    has_stale_domains: bool = False
    missing_domains: tuple[str, ...] = field(default_factory=tuple)
    stale_domains: tuple[str, ...] = field(default_factory=tuple)
    contested_fields: tuple[str, ...] = field(default_factory=tuple)
    corrupted_fields: tuple[str, ...] = field(default_factory=tuple)
    topology_unavailable: bool = False


ALL_DOMAINS: tuple[str, ...] = (
    "worker",
    "zone",
    "equipment",
    "permit",
    "sensor",
    "incident",
    "maintenance",
)


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Aggregate Root. Immutable, read-only snapshot for the duration of
    one scoring cycle (Phase 2.2 §5.4). Produced by
    `ContextBuilder.snapshot()`.
    """

    zone_id: str
    site_id: str
    snapshot_at: datetime

    site: SiteContext | None
    zone: ZoneContext | None
    workers: tuple[WorkerContext, ...]
    equipment: tuple[EquipmentContext, ...]
    permits: tuple[PermitContext, ...]
    sensor: SensorContext | None
    incident: IncidentContext | None
    maintenance: tuple[MaintenanceContext, ...]
    historical: HistoricalContext | None
    neighbor_zones: tuple[NeighborZoneContext, ...]

    operational_timeline: OperationalTimeline
    evidence: EvidenceCollection
    correlation_findings: tuple[CorrelationFinding, ...]

    confidence_model: ConfidenceModel
    version_metadata: VersionMetadata
    correlation_metadata: CorrelationMetadata
    quality: ContextQuality

    def with_correlation_findings(
        self, findings: tuple[CorrelationFinding, ...]
    ) -> "RiskContext":
        """Correlation phase attaches its output without touching any
        other field — RiskContext stays otherwise immutable per snapshot."""
        import dataclasses

        return dataclasses.replace(self, correlation_findings=findings)
