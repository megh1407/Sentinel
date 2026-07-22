"""GraphRepositoryPort (FRS §7). Abstract contract only.
Implemented by memory/adapters/neo4j_graph_adapter.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext


class GraphRepositoryPort(ABC):
    @abstractmethod
    async def get_neighbor_zones(self, zone_id: str) -> tuple[NeighborZoneContext, ...]:
        """Structural spatial enrichment (Phase 2.2 §7, §10). Degrades to
        an empty tuple, flagged `topology_unavailable` by the caller, on
        Neo4j unavailability — never raises (Phase 2.2 §14)."""
        raise NotImplementedError

    @abstractmethod
    async def query_relationship_path(self, entity_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Conditional deep-traversal path (Phase 2.3 §4.4) — bounded
        multi-hop query, only invoked when cheaper correlation types
        don't already resolve a needed relationship. Not exercised by
        this implementation phase's CorrelationEngine (context-only
        relationship discovery uses structural correlation only), but
        declared here for the port's completeness."""
        raise NotImplementedError
