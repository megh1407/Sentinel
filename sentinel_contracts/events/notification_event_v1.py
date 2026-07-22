from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    DASHBOARD = "DASHBOARD"


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class NotificationEventPayload(BaseModel):
    notification_id: str
    channel: NotificationChannel
    recipient_ref: str
    related_action_id: str | None = None
    related_alert_id: str | None = None
    delivery_status: DeliveryStatus
    retry_attempt: int = 0


class NotificationEvent(BaseModel):
    """Published by the Notification Agent to record a delivery attempt across a communication channel. Not decision-bearing (a delivery record, not a finding)."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'NotificationEvent'
    event_version: int = 1
    event_timestamp: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    producer_service: str = 'notification-agent'
    producer_version: str
    site_id: str
    zone_id: str | None = None
    partition_key: str
    trace_id: str | None = None
    metadata: Metadata
    payload: NotificationEventPayload


class NotificationEventV1(NotificationEvent):
    """Versioned, registry-addressable alias of NotificationEvent (schema subject 'NotificationEvent-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'NotificationEvent-value'
