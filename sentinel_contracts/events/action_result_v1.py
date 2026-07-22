from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class ActionOutcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ActionResultPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['executed_at']
    action_id: str
    outcome: ActionOutcome
    approved_by: str | None = None
    executed_at: datetime | None = None
    failure_reason: str | None = None
    downstream_confirmation: str | None = None


class ActionResult(BaseModel):
    """Outcome of an Action's status transition, owned by the Action Context (produced only by the Action Policy Gateway). Action Event category."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'ActionResult'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    payload: ActionResultPayload


class ActionResultV1(ActionResult):
    """Versioned, registry-addressable alias of ActionResult (schema subject 'ActionResult-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'ActionResult-value'
