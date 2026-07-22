from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.geo_location import GeoLocation
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class SensorType(str, Enum):
    GAS = "GAS"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    VIBRATION = "VIBRATION"
    PROXIMITY = "PROXIMITY"
    SMOKE = "SMOKE"
    HUMIDITY = "HUMIDITY"


class SensorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FAULTY = "FAULTY"
    DECOMMISSIONED = "DECOMMISSIONED"


class SensorEventPayload(BaseModel):
    sensor_id: str
    sensor_type: SensorType
    value: float
    unit: str
    threshold_breached: bool
    sensor_status: SensorStatus = SensorStatus.ACTIVE
    location: GeoLocation | None = None
    raw_metadata: dict[str, str] = Field(default_factory=dict)


class SensorEvent(BaseModel):
    """Raw sensor reading, owned by the Environmental Context. Ingestion Event category."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'SensorEvent'
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
    payload: SensorEventPayload


class SensorEventV1(SensorEvent):
    """Versioned, registry-addressable alias of SensorEvent (schema subject 'SensorEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'SensorEvent-value'
