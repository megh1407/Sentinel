"""memory/adapters/neo4j_graph_adapter.py — wraps
`sentinel_state.graph_repositories` (Phase 3.1 §2).

Bounded multi-hop traversals only (Neo4j Graph Integration Design §6.2);
`query_relationship_path` is declared for port completeness but is not
invoked by this implementation phase's CorrelationEngine (structural
correlation only, Phase 2.3 §4.4's "on-demand" path is deferred).
"""

from __future__ import annotations

import logging

from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext
from risk_orchestrator_agent.domain.ports.graph_repository_port import GraphRepositoryPort

logger = logging.getLogger(__name__)


class Neo4jUnavailableError(Exception):
    """Raised (caught at spatial_enrichment's boundary, Phase 2.2 §14)
    when the Neo4j driver signals unavailability."""


class Neo4jGraphAdapter(GraphRepositoryPort):
    def __init__(self, driver) -> None:
        """`driver` is an already-constructed async Neo4j driver,
        injected by `agent.py`'s composition root."""
        self._driver = driver

    async def get_neighbor_zones(self, zone_id: str) -> tuple[NeighborZoneContext, ...]:
        query = (
            "MATCH (z:Zone {zone_id: $zone_id})-[r:NEIGHBOR_OF]->(n:Zone) "
            "RETURN n.zone_id AS neighbor_zone_id, n.current_status AS neighbor_state, "
            "r.distance_m AS distance_m, r.relationship_type AS relationship_type "
            "LIMIT 25"
        )
        try:
            async with self._driver.session() as session:
                result = await session.run(query, zone_id=zone_id)
                records = [record async for record in result]
        except Exception as exc:  # noqa: BLE001
            raise Neo4jUnavailableError(str(exc)) from exc
        return tuple(
            NeighborZoneContext(
                neighbor_zone_id=r["neighbor_zone_id"],
                neighbor_state=r.get("neighbor_state"),
                distance_m=r.get("distance_m"),
                relationship_type=r.get("relationship_type") or "adjacent",
            )
            for r in records
        )

    async def query_relationship_path(self, entity_ids: tuple[str, ...]) -> tuple[str, ...]:
        # Bounded to 4 hops per the Neo4j design's optimization rule
        # (Section 6.2) — not exercised by this implementation phase.
        raise NotImplementedError(
            "Deep knowledge-graph traversal is out of scope for this implementation phase"
        )
