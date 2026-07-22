from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class PermitType(str, Enum):
    HOT_WORK = "HOT_WORK"
    CONFINED_SPACE = "CONFINED_SPACE"
    ELECTRICAL = "ELECTRICAL"
    HEIGHT = "HEIGHT"
    EXCAVATION = "EXCAVATION"
    LIFTING = "LIFTING"


class PermitStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


class PermitConditionRef(BaseModel):
    condition_id: str
    description: str
    is_satisfied: bool


class PermitEventPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['valid_from', 'valid_until']
    permit_id: str
    permit_type: PermitType
    status: PermitStatus
    issued_to_worker_id: str
    valid_from: datetime
    valid_until: datetime
    conditions: list[PermitConditionRef] = Field(default_factory=list)


class PermitEvent(BaseModel):
    """Permit-to-Work lifecycle transition, owned by the Permit Context. Ingestion Event category."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'PermitEvent'
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
    payload: PermitEventPayload


class PermitEventV1(PermitEvent):
    """Versioned, registry-addressable alias of PermitEvent (schema subject 'PermitEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'PermitEvent-value'
