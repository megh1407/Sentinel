from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class PermitViolationType(str, Enum):
    EXPIRED_BUT_ACTIVE = "EXPIRED_BUT_ACTIVE"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    CONFLICTING_PERMITS = "CONFLICTING_PERMITS"
    CONDITION_VIOLATED = "CONDITION_VIOLATED"


class PermitViolationDetectedPayload(BaseModel):
    permit_id: str
    violation_type: PermitViolationType


class PermitViolationDetected(BaseModel):
    """Published by the Permit Intelligence Agent when a permit rule is violated. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'PermitViolationDetected'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'permit-intelligence-agent'
    producer_version: str
    site_id: str
    zone_id: str
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    explanation: ExplanationObject
    payload: PermitViolationDetectedPayload


class PermitViolationDetectedV1(PermitViolationDetected):
    """Versioned, registry-addressable alias of PermitViolationDetected (schema subject 'PermitViolationDetected-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'PermitViolationDetected-value'
