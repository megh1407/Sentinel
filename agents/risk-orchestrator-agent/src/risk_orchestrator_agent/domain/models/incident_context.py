"""IncidentContext value object (Phase 2.2 §4.1, §4.2).

Arrives pre-resolved from Incident Intelligence Agent's own Vector DB
pipeline — this component never queries a vector store directly
(Phase 2.2 §14, ALDS §2.6). `knowledge_graph_paths` is likewise
pre-computed by that agent, distinct from ContextBuilder's own direct
Neo4j enrichment (Phase 2.2 §4.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class SimilarIncident:
    incident_id: str
    similarity: float
    incident_type: str
    severity: str
    site_id: str
    occurred_at: datetime
    outcome: str
    root_cause: str
    vector_source: str


@dataclass(frozen=True, slots=True)
class KGPath:
    path: str


@dataclass(frozen=True, slots=True)
class IncidentContext:
    similar_incidents: tuple[SimilarIncident, ...]
    historical_evidence: tuple[str, ...]
    knowledge_graph_paths: tuple[KGPath, ...]
    confidence: ConfidenceScore
    analyzed_at: datetime
    age: Age
    stale: bool = False
