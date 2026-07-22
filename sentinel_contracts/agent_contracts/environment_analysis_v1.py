"""Generated from contracts/agent-contracts/v1/EnvironmentAnalysis.avsc. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py

Restored following the exact same mechanical pattern already established by
sentinel_contracts/agent_contracts/permit_analysis_v1.py (see this repo's
PermitAnalysis_field_mapping.md for the convention this mirrors). No field
was invented or changed: every field, type, enum, and default below is
copied directly from EnvironmentAnalysis.avsc as it exists on disk today.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from ..common.explanation_object import ExplanationObject
from ..common.metadata import Metadata
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
    sensor_ids: list[str] = []


class EnvironmentAnalysisPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['analyzed_at']
    risk_score: float
    confidence: float
    hazards: list[HazardReading] = []
    evacuation_required: bool | None = None
    affected_zones: list[str] = []
    evidence: list[str]
    recommendations: list[str]
    analyzed_at: datetime


class EnvironmentAnalysis(BaseModel):
    """Avro translation of contracts/agent-contracts/v1/environment_analysis.schema.json per the same inlining pattern used by ZoneAnalysis.avsc / PermitAnalysis.avsc / WorkerAnalysis.avsc / MaintenanceAnalysis.avsc / IncidentAnalysis.avsc. Avro has no inheritance, so the BaseEvent envelope and the AgentResult provenance/decision-metadata fields are inlined directly here rather than referenced."""
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
