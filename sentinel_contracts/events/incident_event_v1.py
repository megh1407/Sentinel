from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class IncidentSeverity(str, Enum):
    NEAR_MISS = "NEAR_MISS"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class IncidentEventPayload(BaseModel):
    incident_id: str
    incident_type: str
    severity: IncidentSeverity
    description: str | None = None
    linked_permit_id: str | None = None
    linked_worker_ids: list[str] = Field(default_factory=list)
    linked_asset_ids: list[str] = Field(default_factory=list)
    auto_drafted: bool = False


class IncidentEvent(BaseModel):
    """Incident report/update/close event, owned by the Incident Context. Ingestion Event category (raw ground-truth fact, not a decision -- carries no ExplanationObject)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'IncidentEvent'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str
    producer_version: str
    site_id: str
    zone_id: str
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    payload: IncidentEventPayload


class IncidentEventV1(IncidentEvent):
    """Versioned, registry-addressable alias of IncidentEvent (schema subject 'IncidentEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'IncidentEvent-value'
