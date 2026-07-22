"""memory/repository_manager.py — RepositoryManager (Phase 2.1 §3.10).

Composes the three adapters behind `domain/ports/*`. Owns connection
pooling ownership boundary only (the actual pools are constructed by
`agent.py`'s composition root and injected here, per ALDS §3.2 — this
class does not open connections itself).
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.ports.context_repository_port import ContextRepositoryPort
from risk_orchestrator_agent.domain.ports.graph_repository_port import GraphRepositoryPort
from risk_orchestrator_agent.domain.ports.history_repository_port import HistoryRepositoryPort
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter
from risk_orchestrator_agent.memory.adapters.postgres_history_adapter import (
    PostgresHistoryAdapter,
)
from risk_orchestrator_agent.memory.adapters.neo4j_graph_adapter import Neo4jGraphAdapter


class RepositoryManager:
    """Aggregates the three store-specific adapters and exposes each as
    its port (Phase 2.1 §3.10). `ContextBuilder` et al. are injected with
    `repository_manager.context_repository` etc. — never with this class
    itself — preserving Interface Segregation (Phase 2.1 §12.1)."""

    def __init__(
        self,
        context_repository: ContextRepositoryPort,
        history_repository: HistoryRepositoryPort | None = None,
        graph_repository: GraphRepositoryPort | None = None,
    ) -> None:
        self.context_repository: ContextRepositoryPort = context_repository
        self.history_repository: HistoryRepositoryPort | None = history_repository
        self.graph_repository: GraphRepositoryPort | None = graph_repository

    @classmethod
    def from_clients(cls, *, redis_client, postgres_pool=None, neo4j_driver=None) -> "RepositoryManager":
        """Convenience factory used by `agent.py`'s composition root."""
        return cls(
            context_repository=RedisContextAdapter(redis_client),
            history_repository=PostgresHistoryAdapter(postgres_pool) if postgres_pool else None,
            graph_repository=Neo4jGraphAdapter(neo4j_driver) if neo4j_driver else None,
        )
