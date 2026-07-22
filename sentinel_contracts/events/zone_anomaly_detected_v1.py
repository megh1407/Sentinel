from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class ZoneAnomalyType(str, Enum):
    OCCUPANCY_EXCEEDED = "OCCUPANCY_EXCEEDED"
    ENVIRONMENTAL_HAZARD = "ENVIRONMENTAL_HAZARD"
    RESTRICTED_AREA_VIOLATION = "RESTRICTED_AREA_VIOLATION"
    ZONE_HEALTH_DEGRADED = "ZONE_HEALTH_DEGRADED"
    PERMIT_CONFLICT = "PERMIT_CONFLICT"
    INCIDENT_FREQUENCY_EXCEEDED = "INCIDENT_FREQUENCY_EXCEEDED"
    REPEATED_ANOMALIES = "REPEATED_ANOMALIES"
    RAPID_STATE_CHANGE = "RAPID_STATE_CHANGE"
    MISSING_SENSOR_DATA = "MISSING_SENSOR_DATA"


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ZoneAnomalyDetectedPayload(BaseModel):
    anomaly_id: str
    anomaly_type: ZoneAnomalyType
    severity: AnomalySeverity


class ZoneAnomalyDetected(BaseModel):
    """Published by the Zone Intelligence Agent when a zone crosses an abnormal condition threshold. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'ZoneAnomalyDetected'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'zone-intelligence-agent'
    producer_version: str
    site_id: str
    zone_id: str
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    explanation: ExplanationObject
    payload: ZoneAnomalyDetectedPayload


class ZoneAnomalyDetectedV1(ZoneAnomalyDetected):
    """Versioned, registry-addressable alias of ZoneAnomalyDetected (schema subject 'ZoneAnomalyDetected-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'ZoneAnomalyDetected-value'
