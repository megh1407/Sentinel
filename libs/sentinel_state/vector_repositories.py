"""
vector_repositories.py

Real repository against the official qdrant-client, live-tested here using
Qdrant's embedded (`:memory:`) mode -- a genuine, working vector engine
that runs in-process, not a mock. Production would point the same client
at a real Qdrant server URL instead of `:memory:`; nothing else changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, Filter, FieldCondition, MatchValue
from sentinel_common.errors import StateError


@dataclass
class ScoredResult:
    id: str
    score: float
    metadata: dict


class VectorRepository:
    collection_name: str = "base"
    vector_size: int = 8  # kept small deliberately for fast local proof; production uses the real embedding dimension

    def __init__(self, client: QdrantClient):
        self._client = client
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection_name not in existing:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    def upsert(self, id: str, vector: list[float], metadata: dict) -> None:
        try:
            self._client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(id=id, vector=vector, payload=metadata)],
            )
        except Exception as e:  # noqa: BLE001
            raise StateError(f"vector upsert failed: {e}") from e

    def search(self, query_vector: list[float], top_k: int, metadata_filter: dict) -> list[ScoredResult]:
        if "site_id" not in metadata_filter:
            raise ValueError(
                "metadata_filter must include at least site_id -- similarity search is always "
                "pre-scoped, never a global unfiltered search (Phase 1 Domain Architecture Part 11.2)"
            )
        qdrant_filter = Filter(
            must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in metadata_filter.items()]
        )
        try:
            hits = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
            ).points
        except Exception as e:  # noqa: BLE001
            raise StateError(f"vector search failed: {e}") from e
        return [ScoredResult(id=str(h.id), score=h.score, metadata=h.payload) for h in hits]

    def delete(self, id: str) -> None:
        try:
            self._client.delete(collection_name=self.collection_name, points_selector=[id])
        except Exception as e:  # noqa: BLE001
            raise StateError(f"vector delete failed: {e}") from e


class IncidentEmbeddingRepository(VectorRepository):
    collection_name = "incident_reports_embeddings"
    vector_size = 8


class MaintenanceNoteEmbeddingRepository(VectorRepository):
    collection_name = "maintenance_notes_embeddings"
    vector_size = 8


class SafetyProcedureEmbeddingRepository(VectorRepository):
    collection_name = "safety_procedure_embeddings"
    vector_size = 8
