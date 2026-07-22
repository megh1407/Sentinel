from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class WorkerRiskType(str, Enum):
    FATIGUE = "FATIGUE"
    PPE_VIOLATION = "PPE_VIOLATION"
    LONE_WORKER_HAZARD = "LONE_WORKER_HAZARD"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    LOCATION_HAZARD = "LOCATION_HAZARD"


class WorkerAtRiskPayload(BaseModel):
    worker_id: str
    risk_type: WorkerRiskType


class WorkerAtRisk(BaseModel):
    """Published by the Worker Intelligence Agent when a worker meets an at-risk condition. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'WorkerAtRisk'
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
    explanation: ExplanationObject
    payload: WorkerAtRiskPayload


class WorkerAtRiskV1(WorkerAtRisk):
    """Versioned, registry-addressable alias of WorkerAtRisk (schema subject 'WorkerAtRisk-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'WorkerAtRisk-value'
