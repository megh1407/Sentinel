"""Generated from contracts/agent-contracts/v1/PermitAnalysis.avsc. DO NOT HAND-EDIT -- regenerate via tools/codegen/avro_to_pydantic.py"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from ..common.explanation_object import ExplanationObject
from ..common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class PermitAnalysisError(BaseModel):
    code: str
    message: str
    retryable: bool


class PermitRiskLevel(str, Enum):
    acceptable = "acceptable"
    elevated = "elevated"
    high = "high"
    unacceptable = "unacceptable"


class PermitConflictSeverity(str, Enum):
    advisory = "advisory"
    warning = "warning"
    blocking = "blocking"


class PermitConflictDetail(BaseModel):
    conflicting_permit_id: str | None = None
    conflict_type: str | None = None
    severity: PermitConflictSeverity | None = None


class PermitAnalysisPayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['analyzed_at']
    permit_id: str
    permit_risk_level: PermitRiskLevel | None = None
    risk_score: float
    confidence: float
    conflicts: list[PermitConflictDetail]
    zone_compatibility: bool | None = None
    zone_risk_at_issuance: float | None = None
    evidence: list[str]
    recommendations: list[str]
    analyzed_at: datetime


class PermitAnalysis(BaseModel):
    """Avro translation of contracts/agent-contracts/v1/permit_analysis.schema.json per the same inlining pattern used by ZoneAnalysis.avsc / EnvironmentAnalysis.avsc / WorkerAnalysis.avsc / MaintenanceAnalysis.avsc / IncidentAnalysis.avsc. Avro has no inheritance, so the BaseEvent envelope and the AgentResult provenance/decision-metadata fields (formerly reached via allOf -> agent_result.schema.json) are inlined directly here rather than referenced. Field-by-field mapping: see PermitAnalysis_field_mapping.md in this directory."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = "PermitAnalysis"
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
    result_type: str = "permit_analysis"
    confidence: float
    processing_time_ms: int
    error: PermitAnalysisError | None = None
    explanation: ExplanationObject
    payload: PermitAnalysisPayload


class PermitAnalysisV1(PermitAnalysis):
    """Versioned, registry-addressable alias of PermitAnalysis (schema subject 'PermitAnalysis-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'PermitAnalysis-value'
