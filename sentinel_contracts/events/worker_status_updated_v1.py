from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class WorkerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FATIGUED = "FATIGUED"
    PPE_NON_COMPLIANT = "PPE_NON_COMPLIANT"
    LONE_WORKER = "LONE_WORKER"
    OFFLINE = "OFFLINE"


class WorkerStatusUpdatedPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['last_updated']
    worker_id: str
    status: WorkerStatus
    fatigue_score: float | None = None
    last_updated: datetime


class WorkerStatusUpdated(BaseModel):
    """Materialized worker-state projection, published by the Worker Intelligence Agent. Not decision-bearing (a status projection, not a finding)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'WorkerStatusUpdated'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'worker-intelligence-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    payload: WorkerStatusUpdatedPayload


class WorkerStatusUpdatedV1(WorkerStatusUpdated):
    """Versioned, registry-addressable alias of WorkerStatusUpdated (schema subject 'WorkerStatusUpdated-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'WorkerStatusUpdated-value'
