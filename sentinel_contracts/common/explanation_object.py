from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sentinel_contracts.common.confidence_score import ConfidenceScore
from sentinel_contracts.common.evidence_item import EvidenceItem
from sentinel_contracts.common.risk_contributor import RiskContributor
from typing import ClassVar
from uuid import UUID


class ExplanationObject(BaseModel):
    """Mandatory 'why' attached to every decision-bearing event (RiskScore, AgentResult, PredictionResult). No agent may emit a finding without a populated ExplanationObject."""
    SCHEMA_TIMESTAMP_FIELDS: ClassVar[list[str]] = ['generated_at']
    summary: str
    confidence: ConfidenceScore
    evidence: list[EvidenceItem]
    reasoning_steps: list[str] = Field(default_factory=list)
    risk_contributors: list[RiskContributor] = Field(default_factory=list)
    rule_metadata: dict[str, str] | None = None
    generated_at: datetime
