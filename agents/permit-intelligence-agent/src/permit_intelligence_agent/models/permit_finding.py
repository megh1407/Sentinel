"""
permit_finding.py

PermitFinding is the agent's internal, in-process representation of a
completed permit analysis -- structurally, it is what a real
`PermitAnalysis` event (contracts/agent-contracts/v1/permit_analysis.schema.json)
would carry. It is deliberately NOT a wire/Kafka contract: no `.avsc`
exists for `PermitAnalysis` anywhere in the repo, and no generated
Pydantic model exists in `sentinel_contracts` for it either (verified --
see README.md's "PERMIT-ANALYSIS-CONTRACT-GAP" section). Publishing a type
that isn't backed by a real schema would make EventProducer.publish() raise
FatalError at the schema_provider.get_schema_and_id() lookup, the same way
it would for any other unregistered event type.

Until that gap is resolved (see README), PermitFinding is folded into the
generic AgentResultV1 envelope by permit_analysis_builder.py. Every field
below maps 1:1 onto a field the JSON Schema declares, so migrating to a
real PermitAnalysisV1 model later is a mechanical rename, not a logic change.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Evaluability(str, Enum):
    """Per Phase 2 rules D/E/F of the integration master prompt: a check is
    never silently skipped or assumed-safe. It is always one of these."""
    EVALUATED = "EVALUATED"
    UNKNOWN = "UNKNOWN"  # input existed in principle but wasn't available this run (e.g. no zone context yet)
    BLOCKED_BY_INPUT_CONTRACT = "BLOCKED_BY_INPUT_CONTRACT"  # field doesn't exist on the canonical input event at all
    NOT_EVALUABLE = "NOT_EVALUABLE"  # required data source doesn't exist anywhere in the platform yet


class PermitConflict(BaseModel):
    conflicting_permit_id: str | None = None
    conflict_type: str
    severity: str  # advisory | warning | blocking


class PermitFinding(BaseModel):
    permit_id: str
    permit_risk_level: str  # acceptable | elevated | high | unacceptable
    risk_score: float  # 0-100
    zone_compatibility: bool | None  # None == UNKNOWN (no zone context available)
    zone_risk_at_issuance: float | None  # None == UNKNOWN
    conflicts: list[PermitConflict] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)  # human-readable rule hits, in firing order
    evaluability: dict[str, str] = Field(default_factory=dict)  # check_name -> Evaluability value
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float
    analyzed_at: datetime
