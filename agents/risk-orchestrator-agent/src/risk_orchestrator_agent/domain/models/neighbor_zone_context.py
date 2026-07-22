"""NeighborZoneContext value object (Phase 2.2 §4.1, §4.2, §10).

Sourced from Neo4j adjacency graph via GraphRepositoryPort — structural
spatial enrichment (Phase 2.2 §7, §10), not a live agent topic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NeighborZoneContext:
    neighbor_zone_id: str
    neighbor_state: str | None
    distance_m: float | None
    relationship_type: str  # adjacent | shares_ventilation | evacuation_route_through
