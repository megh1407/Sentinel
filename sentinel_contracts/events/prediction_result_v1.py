from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Metadata
from typing import ClassVar
from uuid import UUID


class PredictionResultPayload(BaseModel):
    prediction_id: str
    model_name: str
    model_version: str
    subject_ref: str
    predicted_event_type: str
    predicted_probability: float
    prediction_horizon_seconds: int


class PredictionResult(BaseModel):
    """Forward-looking prediction, owned by the Risk Context (produced by Forecasting Agent). Intelligence Event category. Decision-bearing: explanation is REQUIRED."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['event_timestamp']
    event_id: UUID
    event_type: str = 'PredictionResult'
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
    payload: PredictionResultPayload


class PredictionResultV1(PredictionResult):
    """Versioned, registry-addressable alias of PredictionResult (schema subject 'PredictionResult-value', version 1)."""
    SCHEMA_VERSION: ClassVar[int] = 1
    SCHEMA_SUBJECT: ClassVar[str] = 'PredictionResult-value'
