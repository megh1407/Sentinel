"""Abstract repository interfaces.

Every repository is a `typing.Protocol` (CSEGS §2.3's guidance: `Protocol`
for testability boundaries) — structural typing means a test fake needs
no inheritance relationship to be interchangeable with a real adapter.
No implementation lives here; concrete adapters (`memory/adapters/*`,
Phase 3.1 §2) satisfy these contracts in a later phase.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from risk_orchestrator_agent.domain.entities.assessment_entities import HistoricalRisk, RiskAssessment
from risk_orchestrator_agent.domain.entities.context_entities import (
    EquipmentContext,
    IncidentContext,
    NeighborZoneContext,
    RiskContext,
    WorkerContext,
    ZoneContext,
)
from risk_orchestrator_agent.domain.entities.assessment_entities import RecommendationSet


@runtime_checkable
class RiskRepository(Protocol):
    """Persistence boundary for `RiskAssessment` aggregates (Phase 2.5 §11,
    Phase 4.2 §3.1)."""

    async def save(self, assessment: RiskAssessment) -> None: ...
    async def find_by_id(self, assessment_id: str) -> RiskAssessment | None: ...
    async def find_by_zone(
        self, zone_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[RiskAssessment]: ...
    async def exists_by_event_id(self, event_id: str) -> bool: ...


@runtime_checkable
class WorkerRepository(Protocol):
    """Persistence boundary for `WorkerContext` reference data."""

    async def get(self, worker_id: str) -> WorkerContext | None: ...
    async def upsert(self, context: WorkerContext) -> None: ...


@runtime_checkable
class ZoneRepository(Protocol):
    """Persistence boundary for `ZoneContext` reference data."""

    async def get(self, zone_id: str) -> ZoneContext | None: ...
    async def upsert(self, context: ZoneContext) -> None: ...
    async def find_neighbors(self, zone_id: str) -> list[NeighborZoneContext]: ...


@runtime_checkable
class IncidentRepository(Protocol):
    """Persistence boundary for `IncidentContext` reference data."""

    async def get(self, incident_id: str) -> IncidentContext | None: ...
    async def find_similar(self, zone_id: str, *, top_k: int = 5) -> list[IncidentContext]: ...


@runtime_checkable
class EquipmentRepository(Protocol):
    """Persistence boundary for `EquipmentContext` reference data."""

    async def get(self, equipment_id: str) -> EquipmentContext | None: ...
    async def upsert(self, context: EquipmentContext) -> None: ...


@runtime_checkable
class RecommendationRepository(Protocol):
    """Persistence boundary for `RecommendationSet` records
    (Phase 2.5 §11 — contained within the Assessment Repository's own
    record in the real schema, Phase 4.2 §3.7; exposed here as its own
    narrow interface for callers that only need recommendation access)."""

    async def save(self, recommendation_set: RecommendationSet) -> None: ...
    async def find_by_assessment(self, assessment_id: str) -> RecommendationSet | None: ...


@runtime_checkable
class HistoricalRepository(Protocol):
    """Persistence boundary for durable severity/trend history
    (Phase 2.2 §3, `HistoricalContext` source)."""

    async def get_previous_severity(self, zone_id: str) -> str | None: ...
    async def get_recent_transitions(self, zone_id: str, *, limit: int = 20) -> list[HistoricalRisk]: ...
    async def append(self, record: HistoricalRisk) -> None: ...


@runtime_checkable
class ContextRepository(Protocol):
    """Persistence boundary for the rolling, Redis-backed `RiskContext`
    (Phase 2.2 §5, realizes `ContextRepositoryPort` from FRS §7)."""

    async def get(self, zone_id: str) -> RiskContext | None: ...
    async def put(self, zone_id: str, context: RiskContext) -> None: ...
    async def expire(self, zone_id: str) -> None: ...
