from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class RecommendedActionType(str, Enum):
    ALERT_OPERATOR = "ALERT_OPERATOR"
    SUSPEND_PERMIT = "SUSPEND_PERMIT"
    EVACUATE_ZONE = "EVACUATE_ZONE"
    NOTIFY_MAINTENANCE = "NOTIFY_MAINTENANCE"
    LOCKOUT_REQUEST = "LOCKOUT_REQUEST"
    STOP_WORK = "STOP_WORK"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    IMMEDIATE = "IMMEDIATE"


class ActionRecommendationPayload(BaseModel):
    recommendation_id: str
    risk_id: str
    recommended_action_type: RecommendedActionType
    priority: RecommendationPriority


class ActionRecommendation(BaseModel):
    """Published by the Action Recommendation Agent as an advisory suggestion, consumed by a human operator or by Response/Action Policy Gateway as input (never auto-executed from this event alone -- only an ActionRequest can trigger the approval workflow). Decision-bearing: explanation REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'ActionRecommendation'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'action-recommendation-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    explanation: ExplanationObject
    payload: ActionRecommendationPayload


class ActionRecommendationV1(ActionRecommendation):
    """Versioned, registry-addressable alias of ActionRecommendation (schema subject 'ActionRecommendation-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'ActionRecommendation-value'
