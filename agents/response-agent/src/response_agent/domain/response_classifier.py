"""
response_classifier.py

Maps (RiskScoreLevel, EmergencyDecision) -> ResponseSeverity (master prompt
SS3). Kept as its own tiny module, separate from emergency_evaluator.py,
because it is a genuinely different question: emergency_evaluator answers
"did an emergency policy fire", this answers "given that, and given the
raw risk band, what is the overall required response severity". A HIGH
risk score with no emergency trigger is HIGH_PRIORITY, not EMERGENCY; a
MEDIUM risk score WITH a confirmed emergency trigger (e.g. confirmed human
exposure combined with a cascading control failure) is escalated to
EMERGENCY even though the risk band itself never left MEDIUM -- this is
the asymmetry the master prompt SS2 calls out explicitly in both
directions.
"""
from __future__ import annotations

from sentinel_contracts.events.risk_score_v1 import RiskScoreLevel

from response_agent.domain.emergency_evaluator import EmergencyDecision
from response_agent.domain.enums import ResponseSeverity

_BAND_TO_SEVERITY: dict[RiskScoreLevel, ResponseSeverity] = {
    RiskScoreLevel.LOW: ResponseSeverity.ADVISORY,
    RiskScoreLevel.MEDIUM: ResponseSeverity.WARNING,
    RiskScoreLevel.HIGH: ResponseSeverity.HIGH_PRIORITY,
    RiskScoreLevel.CRITICAL: ResponseSeverity.CRITICAL,
    RiskScoreLevel.LOCKDOWN: ResponseSeverity.EMERGENCY,
}


def classify_response(risk_level: RiskScoreLevel, emergency: EmergencyDecision) -> ResponseSeverity:
    if emergency.emergency_triggered:
        return ResponseSeverity.EMERGENCY
    return _BAND_TO_SEVERITY[risk_level]
