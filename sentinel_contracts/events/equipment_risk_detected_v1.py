from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class EquipmentRiskType(str, Enum):
    PREDICTED_FAILURE = "PREDICTED_FAILURE"
    ABNORMAL_VIBRATION = "ABNORMAL_VIBRATION"
    ABNORMAL_TEMPERATURE = "ABNORMAL_TEMPERATURE"
    DEPENDENCY_RISK = "DEPENDENCY_RISK"


class EquipmentRiskDetectedPayload(BaseModel):
    asset_id: str
    risk_type: EquipmentRiskType


class EquipmentRiskDetected(BaseModel):
    """Published by the Equipment Intelligence Agent when equipment shows an elevated risk signal. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'EquipmentRiskDetected'
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
    payload: EquipmentRiskDetectedPayload


class EquipmentRiskDetectedV1(EquipmentRiskDetected):
    """Versioned, registry-addressable alias of EquipmentRiskDetected (schema subject 'EquipmentRiskDetected-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'EquipmentRiskDetected-value'
