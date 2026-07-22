"""
graph_projection_service.py

GraphProjectionService -- the class spec Part 17's diagram names explicitly.
It's a thin wrapper around the ALREADY-BUILT ZoneGraphRepository/
AssetGraphRepository (libs/sentinel_state/graph_repositories.py), not a
reimplementation -- those repositories are real code against the official
neo4j driver, matching the Phase 1 graph schema exactly.

HONEST STATUS, inherited from graph_repositories.py's own docstring: this
is NOT live-tested in this environment. Neo4j isn't apt-installable here
and there's no network path to fetch it, so unlike Postgres and Qdrant
(both verified against real running instances this session), this has only
been code-reviewed against the real neo4j driver's API shape.

Deliberately no-op-safe: if the agent's StateContainer wasn't built with a
neo4j_driver (self.state.zone_graph / .asset_graph are None), every method
here silently does nothing rather than raising. Zone Intelligence Agent's
core rule logic must keep working with ZERO Neo4j dependency, exactly like
it does today -- graph projection is additive enrichment, never a
requirement for correctness.
"""
from __future__ import annotations


class GraphProjectionService:
    def __init__(self, zone_graph, asset_graph):
        self._zone_graph = zone_graph
        self._asset_graph = asset_graph

    @property
    def available(self) -> bool:
        return self._zone_graph is not None

    def project_worker_entry(self, zone_id: str, worker_id: str) -> None:
        if self._zone_graph is not None:
            self._zone_graph.upsert_worker_presence(zone_id, worker_id)

    def project_worker_exit(self, zone_id: str, worker_id: str) -> None:
        if self._zone_graph is not None:
            self._zone_graph.remove_worker_presence(zone_id, worker_id)

    def project_permit(self, zone_id: str, permit_id: str, permit_type: str, status: str) -> None:
        if self._zone_graph is not None:
            self._zone_graph.upsert_permit(zone_id, permit_id, permit_type, status)

    def project_incident(self, zone_id: str, incident_id: str, incident_type: str, severity: str) -> None:
        if self._zone_graph is not None:
            self._zone_graph.upsert_incident(zone_id, incident_id, incident_type, severity)

    def project_equipment(self, zone_id: str, asset_id: str, criticality: str = "MEDIUM") -> None:
        if self._asset_graph is not None:
            self._asset_graph.upsert_asset(asset_id, zone_id, criticality)
