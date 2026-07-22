"""
graph_repositories.py

Real code against the official `neo4j` Python driver's actual API. NOT
live-tested in this environment (no Neo4j server reachable -- it isn't
apt-installable and there's no network path to download it). Treat this as
code-reviewed, not execution-verified, until run against
`scripts/dev-env`'s Neo4j container or a real instance. The query shapes
match the Phase 1 Domain Architecture Part 11.1 graph schema exactly.
"""
from __future__ import annotations

from neo4j import Driver
from sentinel_common.errors import StateError


class GraphRepository:
    def __init__(self, driver: Driver):
        self._driver = driver

    def run_query(self, cypher: str, parameters: dict) -> list[dict]:
        try:
            with self._driver.session() as session:
                result = session.run(cypher, parameters)
                return [record.data() for record in result]
        except Exception as e:  # noqa: BLE001 -- neo4j driver raises its own exception hierarchy
            raise StateError(f"Neo4j query failed: {e}") from e


class ZoneGraphRepository(GraphRepository):
    def upsert_zone(self, zone_id: str, site_id: str, name: str, zone_type: str) -> None:
        self.run_query(
            """
            MERGE (z:Zone {zone_id: $zone_id})
            SET z.site_id = $site_id, z.name = $name, z.zone_type = $zone_type
            MERGE (s:Site {site_id: $site_id})
            MERGE (z)-[:PART_OF]->(s)
            """,
            {"zone_id": zone_id, "site_id": site_id, "name": name, "zone_type": zone_type},
        )

    def upsert_adjacency(self, zone_id_a: str, zone_id_b: str) -> None:
        self.run_query(
            """
            MATCH (a:Zone {zone_id: $a}), (b:Zone {zone_id: $b})
            MERGE (a)-[:ADJACENT_TO]->(b)
            MERGE (b)-[:ADJACENT_TO]->(a)
            """,
            {"a": zone_id_a, "b": zone_id_b},
        )

    def get_adjacent_zones(self, zone_id: str, max_hops: int = 2) -> list[str]:
        rows = self.run_query(
            f"""
            MATCH (z:Zone {{zone_id: $zone_id}})-[:ADJACENT_TO*1..{int(max_hops)}]-(other:Zone)
            RETURN DISTINCT other.zone_id AS zone_id
            """,
            {"zone_id": zone_id},
        )
        return [r["zone_id"] for r in rows]

    def get_zones_with_active_hazard_permits(self, zone_id: str, permit_types: list[str]) -> list[str]:
        rows = self.run_query(
            """
            MATCH (z:Zone {zone_id: $zone_id})<-[:ADJACENT_TO*0..2]-(nearby:Zone)
            MATCH (nearby)<-[:ISSUED_FOR]-(p:Permit)
            WHERE p.permit_type IN $permit_types AND p.status = 'ACTIVE'
            RETURN DISTINCT nearby.zone_id AS zone_id
            """,
            {"zone_id": zone_id, "permit_types": permit_types},
        )
        return [r["zone_id"] for r in rows]

    def upsert_worker_presence(self, zone_id: str, worker_id: str) -> None:
        """Zone->Worker (spec Part 6's graph relationship set)."""
        self.run_query(
            """
            MERGE (w:Worker {worker_id: $worker_id})
            MERGE (z:Zone {zone_id: $zone_id})
            MERGE (w)-[:PRESENT_IN]->(z)
            """,
            {"zone_id": zone_id, "worker_id": worker_id},
        )

    def remove_worker_presence(self, zone_id: str, worker_id: str) -> None:
        self.run_query(
            """
            MATCH (w:Worker {worker_id: $worker_id})-[r:PRESENT_IN]->(z:Zone {zone_id: $zone_id})
            DELETE r
            """,
            {"zone_id": zone_id, "worker_id": worker_id},
        )

    def upsert_permit(self, zone_id: str, permit_id: str, permit_type: str, status: str) -> None:
        """Zone->Permit, via Permit-[:ISSUED_FOR]->Zone (matches the existing
        hazard-permit query's edge direction above)."""
        self.run_query(
            """
            MERGE (p:Permit {permit_id: $permit_id})
            SET p.permit_type = $permit_type, p.status = $status
            MERGE (z:Zone {zone_id: $zone_id})
            MERGE (p)-[:ISSUED_FOR]->(z)
            """,
            {"zone_id": zone_id, "permit_id": permit_id, "permit_type": permit_type, "status": status},
        )

    def upsert_incident(self, zone_id: str, incident_id: str, incident_type: str, severity: str) -> None:
        """Zone->Incident (spec Part 6's graph relationship set)."""
        self.run_query(
            """
            MERGE (i:Incident {incident_id: $incident_id})
            SET i.incident_type = $incident_type, i.severity = $severity
            MERGE (z:Zone {zone_id: $zone_id})
            MERGE (i)-[:OCCURRED_IN]->(z)
            """,
            {"zone_id": zone_id, "incident_id": incident_id, "incident_type": incident_type, "severity": severity},
        )


class AssetGraphRepository(GraphRepository):
    def upsert_asset(self, asset_id: str, zone_id: str, criticality: str) -> None:
        self.run_query(
            """
            MERGE (a:Asset {asset_id: $asset_id})
            SET a.criticality = $criticality
            MERGE (z:Zone {zone_id: $zone_id})
            MERGE (a)-[:LOCATED_IN]->(z)
            """,
            {"asset_id": asset_id, "zone_id": zone_id, "criticality": criticality},
        )

    def upsert_dependency(self, asset_id: str, depends_on_asset_id: str) -> None:
        self.run_query(
            """
            MATCH (a:Asset {asset_id: $asset_id}), (b:Asset {asset_id: $depends_on})
            MERGE (a)-[:DEPENDS_ON]->(b)
            """,
            {"asset_id": asset_id, "depends_on": depends_on_asset_id},
        )

    def get_dependency_chain(self, asset_id: str) -> list[str]:
        rows = self.run_query(
            """
            MATCH (a:Asset {asset_id: $asset_id})-[:DEPENDS_ON*]->(dep:Asset)
            RETURN DISTINCT dep.asset_id AS asset_id
            """,
            {"asset_id": asset_id},
        )
        return [r["asset_id"] for r in rows]
