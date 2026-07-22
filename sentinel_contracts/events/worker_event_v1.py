from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.geo_location import GeoLocation
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class WorkerEventKind(str, Enum):
    ZONE_ENTRY = "ZONE_ENTRY"
    ZONE_EXIT = "ZONE_EXIT"
    PPE_STATUS = "PPE_STATUS"
    BIOMETRIC_ALERT = "BIOMETRIC_ALERT"


class WorkerEventPayload(BaseModel):
    worker_id: str
    event_kind: WorkerEventKind
    ppe_status: dict[str, bool] | None = None
    location: GeoLocation | None = None


class WorkerEvent(BaseModel):
    """Pseudonymous worker presence/PPE event, owned by the Worker Context. Ingestion Event category. MUST NOT contain raw PII fields -- enforced by codegen lint against a banned-field-name list (name, email, phone, ssn, badge_photo, etc)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'WorkerEvent'
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
    payload: WorkerEventPayload


class WorkerEventV1(WorkerEvent):
    """Versioned, registry-addressable alias of WorkerEvent (schema subject 'WorkerEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'WorkerEvent-value'
