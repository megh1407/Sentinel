"""Generated from contracts/agent-contracts/v1/EnvironmentAnalysis.avsc. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class EnvironmentAnalysisError(BaseModel):
    code: str
    message: str
    retryable: bool


class HazardType(str, Enum):
    flammable_gas = "flammable_gas"
    toxic_gas = "toxic_gas"
    oxygen_deficiency = "oxygen_deficiency"
    high_temperature = "high_temperature"
    high_pressure = "high_pressure"
    chemical_exposure = "chemical_exposure"
    radiation = "radiation"


class HazardTrend(str, Enum):
    rising = "rising"
    stable = "stable"
    falling = "falling"


class HazardReading(BaseModel):
    hazard_type: HazardType | None = None
    measured_value: float | None = None
    unit: str | None = None
    threshold_ppm: float | None = None
    threshold_breach: bool | None = None
    trend: HazardTrend | None = None
    sensor_ids: list[str] = Field(default_factory=list)


class EnvironmentAnalysisPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['analyzed_at']
    risk_score: float
    confidence: float
    hazards: list[HazardReading] = Field(default_factory=list)
    evacuation_required: bool | None = None
    affected_zones: list[str] = Field(default_factory=list)
    evidence: list[str]
    recommendations: list[str]
    analyzed_at: datetime


class EnvironmentAnalysis(BaseModel):
    """Avro translation of contracts/agent-contracts/v1/environment_analysis.schema.json per Artifact 7 §3's inlining pattern (Artifact 12 Phase 3 Step 9)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = "EnvironmentAnalysis"
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
    agent_id: str
    agent_version: str
    input_events: list[UUID]
    result_type: str = "environment_analysis"
    confidence: float
    processing_time_ms: int
    error: EnvironmentAnalysisError | None = None
    explanation: ExplanationObject
    payload: EnvironmentAnalysisPayload


class EnvironmentAnalysisV1(EnvironmentAnalysis):
    """Versioned, registry-addressable alias of EnvironmentAnalysis (schema subject 'EnvironmentAnalysis-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'EnvironmentAnalysis-value'
