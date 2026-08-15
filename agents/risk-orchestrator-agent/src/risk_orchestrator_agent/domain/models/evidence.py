"""EvidenceItem value object (Phase 2.2 §11.1).

Every fact held in RiskContext must be traceable to a concrete
EvidenceItem — this is the mechanism that makes Phase 1's platform-wide
explainability mandate (Phase 1 §9.4) achievable at the context-assembly
layer, not just at final publish time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11 -- StrEnum was only added in 3.11
    class StrEnum(str, Enum):
        pass


class EvidenceType(StrEnum):
    """Phase 2.2 §11.1's four evidence types."""

    SENSOR_READING = "sensor_reading"
    AGENT_INFERENCE = "agent_inference"
    HISTORICAL_PRECEDENT = "historical_precedent"
    TOPOLOGY_FACT = "topology_fact"
    MANUAL_OVERRIDE = "manual_override"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """A traceable pointer from a claim to the real, immutable upstream
    event that supports it — never a paraphrase or a summary (Phase 2.5 §2).
    """

    evidence_id: str
    evidence_source: str
    evidence_type: EvidenceType
    confidence: float
    timestamp: datetime
    origin_agent: str
    supporting_event_ids: tuple[str, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)