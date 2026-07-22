from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class AgentResultPayload(BaseModel):
    agent_result_id: str
    agent_name: str
    agent_version: str
    subject_ref: str
    finding: str
    confidence: float


class AgentResult(BaseModel):
    """A finding published by any Intelligence Agent, consumed exclusively by the Risk Orchestrator. Agent Communication Event category. explanation REQUIRED, including for NO_FINDING (proves liveness)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'AgentResult'
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
    payload: AgentResultPayload


class AgentResultV1(AgentResult):
    """Versioned, registry-addressable alias of AgentResult (schema subject 'AgentResult-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'AgentResult-value'
