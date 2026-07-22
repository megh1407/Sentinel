"""PermitContext value object (Phase 2.2 §4.1, §4.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore


@dataclass(frozen=True, slots=True)
class PermitConflict:
    conflicting_permit_id: str
    conflict_type: str
    severity: str


@dataclass(frozen=True, slots=True)
class PermitContext:
    permit_id: str
    permit_risk_level: str | None
    # Carried through from Permit Intelligence; ContextBuilder does not
    # itself detect new conflicts (Phase 2.2 §4.2).
    conflicts: tuple[PermitConflict, ...]
    zone_compatibility: bool | None
    zone_risk_at_issuance: float | None
    confidence: ConfidenceScore
    analyzed_at: datetime
    age: Age
    stale: bool = False
