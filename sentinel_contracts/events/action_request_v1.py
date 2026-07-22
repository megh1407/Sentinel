from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class ActionType(str, Enum):
    ALERT_OPERATOR = "ALERT_OPERATOR"
    SUSPEND_PERMIT = "SUSPEND_PERMIT"
    EVACUATE_ZONE = "EVACUATE_ZONE"
    NOTIFY_MAINTENANCE = "NOTIFY_MAINTENANCE"
    LOCKOUT_REQUEST = "LOCKOUT_REQUEST"


class ActionUrgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    IMMEDIATE = "IMMEDIATE"


class ActionRequestPayload(BaseModel):
    action_id: str
    risk_id: str
    action_type: ActionType
    target_ref: str
    requested_by: str
    urgency: ActionUrgency
    requires_human_approval: bool = True
    requires_dual_control: bool = False


class ActionRequest(BaseModel):
    """A proposed preventive/corrective action, owned by the Action Context (produced by Response Agent or a human operator). Action Event category. justification is REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'ActionRequest'
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
    justification: ExplanationObject
    payload: ActionRequestPayload


class ActionRequestV1(ActionRequest):
    """Versioned, registry-addressable alias of ActionRequest (schema subject 'ActionRequest-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'ActionRequest-value'
