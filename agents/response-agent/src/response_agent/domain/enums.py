"""
enums.py

Internal decision-engine vocabulary. NONE of these are wire contracts --
they never appear in an .avsc file and are never serialized onto a Kafka
topic. They exist purely to make the Response Agent's own reasoning
(response_classifier.py, emergency_evaluator.py) typed and testable.

ResponseSeverity mirrors the ladder in the Response Agent master prompt
SS3 (NORMAL -> ADVISORY -> WARNING -> HIGH_PRIORITY -> CRITICAL ->
EMERGENCY). It is intentionally NOT the same enum as RiskScoreLevel
(sentinel_contracts.events.risk_score_v1.RiskScoreLevel) -- RiskScoreLevel
is Risk Orchestrator's classification of the risk itself; ResponseSeverity
is this agent's own classification of the REQUIRED RESPONSE, which folds
in emergency-trigger evaluation on top of the raw risk band (master prompt
SS2: "Global Risk = HIGH does not automatically mean Emergency = TRUE" --
and the converse also holds, a HIGH score with a confirmed emergency
trigger IS escalated to EMERGENCY response severity even though the risk
band itself stayed HIGH).
"""
from __future__ import annotations

from enum import Enum


class ResponseSeverity(str, Enum):
    NORMAL = "NORMAL"
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


# Ordering for escalation/downgrade comparisons (higher rank == more severe).
# Not an IntEnum on ResponseSeverity itself so the wire-adjacent string enum
# stays a plain str Enum (matches the rest of the codebase's enum style).
SEVERITY_RANK: dict[ResponseSeverity, int] = {
    ResponseSeverity.NORMAL: 0,
    ResponseSeverity.ADVISORY: 1,
    ResponseSeverity.WARNING: 2,
    ResponseSeverity.HIGH_PRIORITY: 3,
    ResponseSeverity.CRITICAL: 4,
    ResponseSeverity.EMERGENCY: 5,
}


class EmergencyTriggerType(str, Enum):
    """Master prompt SS4.A-F. A single EmergencyDecision can carry more
    than one of these (SS4.E: "multiple simultaneous hazards")."""
    LOCKDOWN_BAND = "LOCKDOWN_BAND"  # RiskScoreLevel.LOCKDOWN is, by contract definition, already the terminal band
    IMMEDIATE_THREAT_TO_LIFE = "IMMEDIATE_THREAT_TO_LIFE"
    RAPID_ESCALATION = "RAPID_ESCALATION"
    CROSS_ZONE_PROPAGATION = "CROSS_ZONE_PROPAGATION"
    CASCADE_DETECTED = "CASCADE_DETECTED"
    MULTIPLE_HAZARDS = "MULTIPLE_HAZARDS"
    CRITICAL_CONTROL_FAILURE = "CRITICAL_CONTROL_FAILURE"
