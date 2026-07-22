from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class VectorCollection(str, Enum):
    INCIDENT_REPORTS_EMBEDDINGS = "INCIDENT_REPORTS_EMBEDDINGS"
    MAINTENANCE_NOTES_EMBEDDINGS = "MAINTENANCE_NOTES_EMBEDDINGS"
    SAFETY_PROCEDURE_EMBEDDINGS = "SAFETY_PROCEDURE_EMBEDDINGS"


class EmbeddingsCreatedPayload(BaseModel):
    collection_name: VectorCollection
    vector_id: str
    source_id: str
    source_type: str
    embedding_model_version: str


class EmbeddingsCreated(BaseModel):
    """Published by the Knowledge Context Agent whenever a new vector embedding is stored. Not decision-bearing."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'EmbeddingsCreated'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'knowledge-context-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    payload: EmbeddingsCreatedPayload


class EmbeddingsCreatedV1(EmbeddingsCreated):
    """Versioned, registry-addressable alias of EmbeddingsCreated (schema subject 'EmbeddingsCreated-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'EmbeddingsCreated-value'
