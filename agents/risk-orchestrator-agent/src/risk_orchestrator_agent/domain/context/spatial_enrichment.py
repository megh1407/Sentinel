"""domain/context/spatial_enrichment.py — structural spatial enrichment
(Phase 2.2 §7, §10).

Attaches zone-topology facts (neighboring zones) via `GraphRepositoryPort`.
Never performs semantic enrichment (Phase 2.2 §7.1's enrichment
boundary) — only what is structurally true.
"""

from __future__ import annotations

import logging

from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext
from risk_orchestrator_agent.domain.ports.graph_repository_port import GraphRepositoryPort

logger = logging.getLogger(__name__)


async def enrich_neighbor_zones(
    zone_id: str, graph_port: GraphRepositoryPort | None
) -> tuple[tuple[NeighborZoneContext, ...], bool]:
    """Returns (neighbor_zones, topology_unavailable).

    On Neo4j unavailability, degrades to an empty tuple with
    `topology_unavailable=True` (Phase 2.2 §14) — never blocks the
    cycle, never raises.
    """
    if graph_port is None:
        return (), True
    try:
        neighbors = await graph_port.get_neighbor_zones(zone_id)
        return neighbors, False
    except Exception:  # noqa: BLE001 - degrade, never propagate (Phase 2.2 §14)
        logger.warning("neo4j_unavailable_neighbor_zone_enrichment", extra={"zone_id": zone_id})
        return (), True
