from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class IncidentCorrelationFoundPayload(BaseModel):
    incident_id: str
    correlated_incident_ids: list[str]
    similarity_scores: list[float]


class IncidentCorrelationFound(BaseModel):
    """Published by the Incident Intelligence Agent when it finds similar past incidents. Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'IncidentCorrelationFound'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'incident-intelligence-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    explanation: ExplanationObject
    payload: IncidentCorrelationFoundPayload


class IncidentCorrelationFoundV1(IncidentCorrelationFound):
    """Versioned, registry-addressable alias of IncidentCorrelationFound (schema subject 'IncidentCorrelationFound-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'IncidentCorrelationFound-value'
