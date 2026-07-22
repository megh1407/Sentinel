from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class BaseEvent(BaseModel):
    """Canonical envelope shared by every SENTINEL event. Domain event schemas (contracts/events/*) inline these exact fields plus a payload field, rather than using Avro inheritance (which Avro does not support) -- this record exists as the single documented source of truth for envelope field names/types/order, enforced by a codegen lint that diffs every event schema's envelope fields against this definition."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str
    event_version: int
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str
    producer_version: str
    site_id: str
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
