from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class MaintenanceUrgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MaintenanceRequiredPayload(BaseModel):
    asset_id: str
    urgency: MaintenanceUrgency
    recommended_action: str


class MaintenanceRequired(BaseModel):
    """Published by the Equipment Intelligence Agent as a maintenance recommendation. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'MaintenanceRequired'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'equipment-intelligence-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    explanation: ExplanationObject
    payload: MaintenanceRequiredPayload


class MaintenanceRequiredV1(MaintenanceRequired):
    """Versioned, registry-addressable alias of MaintenanceRequired (schema subject 'MaintenanceRequired-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'MaintenanceRequired-value'
