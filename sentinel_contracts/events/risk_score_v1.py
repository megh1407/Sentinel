from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class RiskScoreLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    LOCKDOWN = "LOCKDOWN"


class RiskScorePayload(BaseModel):
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['valid_until']
    risk_id: str
    score: float
    risk_level: RiskScoreLevel
    contributing_agent_result_ids: list[str] = Field(default_factory=list)
    compound_rules_fired: list[str] = Field(default_factory=list)
    valid_until: datetime


class RiskScore(BaseModel):
    """The core explainable output of the Risk Engine, owned by the Risk Context. Intelligence Event category. Decision-bearing: explanation is REQUIRED, never null."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'RiskScore'
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
    explanation: ExplanationObject
    payload: RiskScorePayload


class RiskScoreV1(RiskScore):
    """Versioned, registry-addressable alias of RiskScore (schema subject 'RiskScore-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'RiskScore-value'
