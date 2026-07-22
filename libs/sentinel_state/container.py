"""
container.py

StateContainer is what sentinel_agent_sdk injects as `self.state` on every
agent. It bundles whichever repositories an agent actually needs -- an
agent using only Redis+Postgres doesn't get a spurious Neo4j/Vector client
constructed (and therefore doesn't need those services reachable to start
up), matching the health-check design in Part 9.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import redis
from neo4j import Driver
from qdrant_client import QdrantClient
from sqlalchemy.orm import sessionmaker

from .graph_repositories import AssetGraphRepository, ZoneGraphRepository
from .postgres_repositories import HelloSeenRepository, ZoneRepository
from .redis_repositories import AnomalyTrackingRepository, HelloStateRepository, IncidentTrackingRepository, ResponseTrackingRepository, StateChangeTrackingRepository, WorkerPresenceRepository, ZoneStateRepository
from .vector_repositories import IncidentEmbeddingRepository, MaintenanceNoteEmbeddingRepository, SafetyProcedureEmbeddingRepository


@dataclass
class StateContainer:
    """Constructed once per agent process by AgentFactory (sentinel_agent_sdk),
    based on which backends that agent's config declares it needs.
    Repository attributes are None if the corresponding backend wasn't
    configured for this agent -- accessing one that's None raises a clear
    AttributeError-style failure at first use, not a silent no-op."""

    redis_client: redis.Redis | None = None
    postgres_session_factory: sessionmaker | None = None
    neo4j_driver: Driver | None = None
    qdrant_client: QdrantClient | None = None

    zone: ZoneStateRepository | None = field(default=None, init=False)
    worker: WorkerPresenceRepository | None = field(default=None, init=False)
    hello: HelloStateRepository | None = field(default=None, init=False)
    incidents: IncidentTrackingRepository | None = field(default=None, init=False)
    anomalies: AnomalyTrackingRepository | None = field(default=None, init=False)
    state_changes: StateChangeTrackingRepository | None = field(default=None, init=False)
    response: ResponseTrackingRepository | None = field(default=None, init=False)
    hello_pg: HelloSeenRepository | None = field(default=None, init=False)
    zone_pg: ZoneRepository | None = field(default=None, init=False)
    zone_graph: ZoneGraphRepository | None = field(default=None, init=False)
    asset_graph: AssetGraphRepository | None = field(default=None, init=False)
    incident_embeddings: IncidentEmbeddingRepository | None = field(default=None, init=False)
    maintenance_embeddings: MaintenanceNoteEmbeddingRepository | None = field(default=None, init=False)
    procedure_embeddings: SafetyProcedureEmbeddingRepository | None = field(default=None, init=False)

    def __post_init__(self):
        if self.redis_client is not None:
            self.zone = ZoneStateRepository(self.redis_client)
            self.worker = WorkerPresenceRepository(self.redis_client)
            self.hello = HelloStateRepository(self.redis_client)
            self.incidents = IncidentTrackingRepository(self.redis_client)
            self.anomalies = AnomalyTrackingRepository(self.redis_client)
            self.state_changes = StateChangeTrackingRepository(self.redis_client)
            self.response = ResponseTrackingRepository(self.redis_client)
        if self.postgres_session_factory is not None:
            self.hello_pg = HelloSeenRepository(self.postgres_session_factory)
            self.zone_pg = ZoneRepository(self.postgres_session_factory)
        if self.neo4j_driver is not None:
            self.zone_graph = ZoneGraphRepository(self.neo4j_driver)
            self.asset_graph = AssetGraphRepository(self.neo4j_driver)
        if self.qdrant_client is not None:
            self.incident_embeddings = IncidentEmbeddingRepository(self.qdrant_client)
            self.maintenance_embeddings = MaintenanceNoteEmbeddingRepository(self.qdrant_client)
            self.procedure_embeddings = SafetyProcedureEmbeddingRepository(self.qdrant_client)

    def health_checks(self) -> dict[str, bool]:
        """Used by sentinel_agent_sdk.health (Part 9) to auto-register only
        the checks relevant to backends this agent actually uses."""
        checks = {}
        if self.redis_client is not None:
            try:
                checks["redis"] = self.redis_client.ping()
            except Exception:
                checks["redis"] = False
        if self.postgres_session_factory is not None:
            try:
                with self.postgres_session_factory() as s:
                    s.execute(__import__("sqlalchemy").text("SELECT 1"))
                checks["postgres"] = True
            except Exception:
                checks["postgres"] = False
        if self.neo4j_driver is not None:
            try:
                self.neo4j_driver.verify_connectivity()
                checks["neo4j"] = True
            except Exception:
                checks["neo4j"] = False
        if self.qdrant_client is not None:
            try:
                self.qdrant_client.get_collections()
                checks["vector_db"] = True
            except Exception:
                checks["vector_db"] = False
        return checks
