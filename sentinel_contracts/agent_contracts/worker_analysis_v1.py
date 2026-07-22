"""Generated from contracts/agent-contracts/v1/WorkerAnalysis.avsc. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py

Restored following the exact same mechanical pattern already established by
sentinel_contracts/agent_contracts/permit_analysis_v1.py and
environment_analysis_v1.py. No field was invented or changed: every field,
type, enum, and default below is copied directly from WorkerAnalysis.avsc as
it exists on disk today.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from ..common.explanation_object import ExplanationObject
from ..common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class WorkerAnalysisError(BaseModel):
    code: str
    message: str
    retryable: bool


class WorkerSafetyStatus(str, Enum):
    safe = "safe"
    at_risk = "at_risk"
    in_danger = "in_danger"
    unresponsive = "unresponsive"


class ProximityAlert(BaseModel):
    hazard_type: str | None = None
    distance_m: float | None = None
    safe_distance_m: float | None = None


class WorkerAnalysisPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['analyzed_at']
    worker_id: str
    risk_score: float
    confidence: float
    safety_status: WorkerSafetyStatus
    ppe_compliance: float | None = None
    ppe_violations: list[str] = []
    zone_clearance: bool | None = None
    proximity_alerts: list[ProximityAlert] = []
    evidence: list[str]
    recommendations: list[str]
    analyzed_at: datetime


class WorkerAnalysis(BaseModel):
    """Avro translation of contracts/agent-contracts/v1/worker_analysis.schema.json per the same inlining pattern used by ZoneAnalysis.avsc / PermitAnalysis.avsc / EnvironmentAnalysis.avsc / MaintenanceAnalysis.avsc / IncidentAnalysis.avsc. Avro has no inheritance, so the BaseEvent envelope and the AgentResult provenance/decision-metadata fields are inlined directly here rather than referenced."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = "WorkerAnalysis"
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
    result_type: str = "worker_analysis"
    confidence: float
    processing_time_ms: int
    error: WorkerAnalysisError | None = None
    explanation: ExplanationObject
    payload: WorkerAnalysisPayload


class WorkerAnalysisV1(WorkerAnalysis):
    """Versioned, registry-addressable alias of WorkerAnalysis (schema subject 'WorkerAnalysis-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'WorkerAnalysis-value'
