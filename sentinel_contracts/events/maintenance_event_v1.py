from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class MaintenanceType(str, Enum):
    SCHEDULED = "SCHEDULED"
    CORRECTIVE = "CORRECTIVE"
    EMERGENCY = "EMERGENCY"


class MaintenanceStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class AssetCriticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MaintenanceEventPayload(BaseModel):
    asset_id: str
    maintenance_order_id: str
    maintenance_type: MaintenanceType
    status: MaintenanceStatus
    overdue_days: int | None = None
    criticality: AssetCriticality


class MaintenanceEvent(BaseModel):
    """Asset maintenance order lifecycle event, owned by the Maintenance Context. Ingestion Event category."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'MaintenanceEvent'
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
    payload: MaintenanceEventPayload


class MaintenanceEventV1(MaintenanceEvent):
    """Versioned, registry-addressable alias of MaintenanceEvent (schema subject 'MaintenanceEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'MaintenanceEvent-value'
