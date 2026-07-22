from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    LOCKDOWN = "LOCKDOWN"


class ZoneStatePayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['last_updated']
    current_risk_level: RiskLevel
    active_permit_ids: list[str] = Field(default_factory=list)
    active_permit_types: dict[str, str] = Field(default_factory=dict)
    occupancy_count: int
    active_sensor_alert_ids: list[str] = Field(default_factory=list)
    active_equipment_risk_ids: list[str] = Field(default_factory=list)
    recent_incident_count: int = 0
    pending_critical_maintenance_asset_ids: list[str] = Field(default_factory=list)
    last_sensor_reading_ts: dict[str, float] = Field(default_factory=dict)
    stale_sensor_ids: list[str] = Field(default_factory=list)
    last_updated: datetime
    is_stale: bool = False


class ZoneState(BaseModel):
    """Materialized 'what's true about this zone right now' projection, owned by the Zone Context. Intelligence Event category."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'ZoneState'
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
    payload: ZoneStatePayload


class ZoneStateV1(ZoneState):
    """Versioned, registry-addressable alias of ZoneState (schema subject 'ZoneState-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'ZoneState-value'
