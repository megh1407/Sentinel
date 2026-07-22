from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class KnowledgeNodeType(str, Enum):
    ZONE = "ZONE"
    ASSET = "ASSET"
    PERMIT = "PERMIT"
    WORKER = "WORKER"
    INCIDENT = "INCIDENT"
    SITE = "SITE"


class KnowledgeOperation(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class KnowledgeUpdatedPayload(BaseModel):
    node_type: KnowledgeNodeType
    node_id: str
    operation: KnowledgeOperation
    source_event_id: str


class KnowledgeUpdated(BaseModel):
    """Published by the Knowledge Context Agent whenever it materializes a graph projection change. Not decision-bearing."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'KnowledgeUpdated'
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
    payload: KnowledgeUpdatedPayload


class KnowledgeUpdatedV1(KnowledgeUpdated):
    """Versioned, registry-addressable alias of KnowledgeUpdated (schema subject 'KnowledgeUpdated-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'KnowledgeUpdated-value'
