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
    calibration_offset: float | None = None
    battery_level_percent: int | None = None


class SensorEvent(BaseModel):
    """v2: additive, backward-compatible evolution of SensorEvent v1. Adds payload.calibration_offset and payload.battery_level_percent as OPTIONAL fields with defaults, per the minor-version rule (Part 5). All v1 consumers can read v2 payloads unmodified (extra fields simply absent from their view); this is proven by test_backward_compatibility.py."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'SensorEvent'
    event_version: int = 2
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


class SensorEventV2(SensorEvent):
    """Versioned, registry-addressable alias of SensorEvent (schema subject 'SensorEvent-value', version 2)."""
    SCHEMA_VERSION: ClassVar[int] = 2
    SCHEMA_SUBJECT: ClassVar[str] = 'SensorEvent-value'
