"""neo4j_topology.py

Seeds and reads the zone topology the Risk Orchestrator's Neo4jGraphAdapter
queries (`(z:Zone)-[:NEIGHBOR_OF]->(n:Zone)` with r.distance_m /
r.relationship_type, n.current_status). This is the single source of the
plant's relationship graph -- the dashboard renders THIS, it does not invent
its own topology.

The seed models the master prompt's multi-zone scenario explicitly:

    ZONE-A --SHARES_VENTILATION_WITH--> ZONE-B
    ZONE-A --ADJACENT_TO------------->  ZONE-C
    ZONE-A --CONNECTED_BY_ROUTE_TO---> ZONE-D   (evacuation route)

Relationships are seeded in both directions so a hazard in any zone can
propagate to its neighbours (the adapter's query is directional). Idempotent
(MERGE), so re-running on startup never duplicates nodes or edges.
"""
from __future__ import annotations

# (from_zone, to_zone, relationship_type, distance_m) -- seeded both ways.
_EDGES: list[tuple[str, str, str, float]] = [
    ("ZONE-A", "ZONE-B", "shares_ventilation", 15.0),
    ("ZONE-A", "ZONE-C", "adjacent", 8.0),
    ("ZONE-A", "ZONE-D", "evacuation_route", 40.0),
    ("ZONE-B", "ZONE-C", "adjacent", 12.0),
]
_ZONES = ["ZONE-A", "ZONE-B", "ZONE-C", "ZONE-D"]


async def seed_default_topology(driver) -> None:
    """Creates the Zone nodes + bidirectional NEIGHBOR_OF edges. Async driver."""
    async with driver.session() as session:
        for z in _ZONES:
            await session.run(
                "MERGE (z:Zone {zone_id: $zone_id}) "
                "ON CREATE SET z.current_status = 'normal'",
                zone_id=z,
            )
        for a, b, rel, dist in _EDGES:
            for src, dst in ((a, b), (b, a)):
                await session.run(
                    "MATCH (s:Zone {zone_id: $src}), (d:Zone {zone_id: $dst}) "
                    "MERGE (s)-[r:NEIGHBOR_OF]->(d) "
                    "SET r.relationship_type = $rel, r.distance_m = $dist",
                    src=src, dst=dst, rel=rel, dist=dist,
                )


async def set_zone_status(driver, zone_id: str, status: str) -> None:
    """Reflects live zone state (e.g. a hazard) onto the graph node so
    neighbour queries return a real current_status."""
    async with driver.session() as session:
        await session.run(
            "MERGE (z:Zone {zone_id: $zone_id}) SET z.current_status = $status",
            zone_id=zone_id, status=status,
        )


def set_zone_status_sync(driver, zone_id: str, status: str) -> None:
    """Sync twin of set_zone_status, for the API gateway's own sync Neo4j
    driver. Without this, current_status is written once at seed time and
    never again -- every node stays 'normal' regardless of real risk."""
    with driver.session() as session:
        session.run(
            "MERGE (z:Zone {zone_id: $zone_id}) SET z.current_status = $status",
            zone_id=zone_id, status=status,
        )


def seed_default_topology_sync(driver) -> None:
    """Sync twin of seed_default_topology, for the API gateway's own sync
    neo4j driver (FastAPI request handlers are sync). Same edges, idempotent."""
    with driver.session() as session:
        for z in _ZONES:
            session.run(
                "MERGE (z:Zone {zone_id: $zone_id}) ON CREATE SET z.current_status = 'normal'",
                zone_id=z,
            )
        for a, b, rel, dist in _EDGES:
            for src, dst in ((a, b), (b, a)):
                session.run(
                    "MATCH (s:Zone {zone_id: $src}), (d:Zone {zone_id: $dst}) "
                    "MERGE (s)-[r:NEIGHBOR_OF]->(d) "
                    "SET r.relationship_type = $rel, r.distance_m = $dist",
                    src=src, dst=dst, rel=rel, dist=dist,
                )


def read_topology_sync(driver) -> dict:
    """Sync twin of read_topology -- what /api/topology serves the dashboard."""
    with driver.session() as session:
        nodes = [
            {"zone_id": r["zone_id"], "current_status": r["status"]}
            for r in session.run("MATCH (z:Zone) RETURN z.zone_id AS zone_id, z.current_status AS status")
        ]
        edges = [
            {"from": r["src"], "to": r["dst"], "relationship_type": r["rel"], "distance_m": r["dist"]}
            for r in session.run(
                "MATCH (s:Zone)-[r:NEIGHBOR_OF]->(d:Zone) "
                "RETURN s.zone_id AS src, d.zone_id AS dst, "
                "r.relationship_type AS rel, r.distance_m AS dist"
            )
        ]
    return {"nodes": nodes, "edges": edges}


async def read_topology(driver) -> dict:
    """Returns {nodes:[{zone_id,current_status}], edges:[{from,to,relationship_type,distance_m}]}
    -- exactly what a frontend graph view needs, derived from Neo4j, not
    hardcoded."""
    async with driver.session() as session:
        node_res = await session.run("MATCH (z:Zone) RETURN z.zone_id AS zone_id, z.current_status AS status")
        nodes = [{"zone_id": r["zone_id"], "current_status": r["status"]} async for r in node_res]
        edge_res = await session.run(
            "MATCH (s:Zone)-[r:NEIGHBOR_OF]->(d:Zone) "
            "RETURN s.zone_id AS src, d.zone_id AS dst, "
            "r.relationship_type AS rel, r.distance_m AS dist"
        )
        edges = [
            {"from": r["src"], "to": r["dst"], "relationship_type": r["rel"], "distance_m": r["dist"]}
            async for r in edge_res
        ]
    return {"nodes": nodes, "edges": edges}
