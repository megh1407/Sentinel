"""
emergency_evaluator.py

Pure decision logic for "is this an emergency" (Response Agent master
prompt SS4-SS6). No I/O, no Kafka, no Redis -- this module takes plain
data in and returns a plain EmergencyDecision out, which is what makes it
unit-testable without any of the SDK's infrastructure (see
tests/unit/test_emergency_evaluator.py).

Ground rule (master prompt SS2): this function NEVER recomputes system
risk. It only reads the fields RiskScoreV1 already carries (plus an
optional previous-risk snapshot supplied by the caller for velocity
detection) and applies emergency POLICY on top of that authoritative
input. It has no opinion on whether the score itself is correct.

What master prompt SS4 conditions are and are NOT evaluated here, and why:

  A. Immediate threat to life       -- evaluated (human_exposure_confirmed
                                        + high risk band)
  B. Rapid escalation                -- evaluated (previous_risk velocity)
  C. Cross-zone propagation          -- evaluated (propagation_paths /
                                        affected_zones)
  D. Cascade-triggered emergency      -- evaluated (cascade_paths)
  E. Multiple simultaneous hazards    -- approximated via
                                        compound_rules_fired count (see
                                        docstring on _multiple_hazards
                                        below for the honest limitation)
  F. Critical safety control failure  -- evaluated (critical_controls_unavailable
                                        + risk band)

SS4.B, C, D, F all depend on the OPTIONAL RiskScorePayload fields added
alongside this agent (affected_zones, affected_assets,
human_exposure_confirmed, critical_controls_unavailable,
propagation_paths, cascade_paths -- see contracts/events/RiskScore/v1/schema.avsc).
Risk Orchestrator (the only real producer of RiskScore) is a separate
agent, out of this task's scope, and does not populate these fields yet
(PLATFORM_GAP -- see README.md). Every check below is written to degrade
gracefully to "condition not detected" when its input field is empty,
per contracts/versioning/compatibility_rules.md's semantics for an
unpopulated optional field ("empty means not populated, not confirmed
absent") -- this module never treats missing data as an all-clear.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sentinel_contracts.events.risk_score_v1 import RiskScoreLevel, RiskScoreV1

from response_agent.domain.enums import EmergencyTriggerType

# Risk score jump (0-100 scale) within a single re-evaluation that counts as
# "rapidly escalating" per master prompt SS4.B, even if the new score
# hasn't yet reached the highest band on its own.
RAPID_ESCALATION_SCORE_DELTA = 30.0

# Risk bands, ordered low -> high, for detecting a multi-band jump (e.g.
# LOW -> HIGH in one step) independent of the raw score delta above.
_BAND_ORDER = [RiskScoreLevel.LOW, RiskScoreLevel.MEDIUM, RiskScoreLevel.HIGH,
               RiskScoreLevel.CRITICAL, RiskScoreLevel.LOCKDOWN]
_BAND_RANK = {band: i for i, band in enumerate(_BAND_ORDER)}
RAPID_ESCALATION_MIN_BAND_JUMP = 2  # e.g. LOW(0) -> HIGH(2) or worse in one step

# A risk band at or above this rank is a prerequisite for SS4.A and SS4.F
# (a control failure or confirmed exposure at LOW/MEDIUM risk is handled as
# an ordinary corrective action, not an emergency -- see SS9).
_HIGH_RISK_MIN_RANK = _BAND_RANK[RiskScoreLevel.HIGH]

# SS4.E's proxy threshold -- see _multiple_hazards().
MULTIPLE_HAZARDS_MIN_COMPOUND_RULES = 2


@dataclass
class PreviousRisk:
    """Caller-supplied snapshot of the last risk score observed for this
    zone (from ResponseTrackingRepository.get_previous_risk), used only for
    SS4.B velocity detection. Not a wire contract."""
    score: float
    risk_level: RiskScoreLevel


@dataclass
class EmergencyDecision:
    """Master prompt SS5's EmergencyDecision, trimmed to what this engine
    can actually populate from a single RiskScoreV1 (affected_personnel and
    evacuation_required are asset-graph/worker-presence questions this
    module does not have data for -- see services/response_service.py for
    where those get folded in from state, when available)."""
    emergency_triggered: bool
    triggers: list[EmergencyTriggerType] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def trigger_reason(self) -> str | None:
        """Single human-readable string for ActionRequestPayload.trigger_reason."""
        return " ".join(self.reasons) if self.reasons else None


def evaluate_emergency(risk: RiskScoreV1, previous: PreviousRisk | None) -> EmergencyDecision:
    """The master prompt SS6 decision hierarchy, condensed: evaluate every
    applicable trigger (not just the first that matches -- SS4.E explicitly
    requires considering combinations), and never let a low `confidence`
    downgrade an otherwise-clear emergency (SS6: "never downgrade a clearly
    immediate emergency to passive monitoring merely because confidence <
    100%"). Confidence is surfaced in the caller's explanation, not used
    here to suppress a trigger.
    """
    payload = risk.payload
    triggers: list[EmergencyTriggerType] = []
    reasons: list[str] = []

    if payload.risk_level == RiskScoreLevel.LOCKDOWN:
        triggers.append(EmergencyTriggerType.LOCKDOWN_BAND)
        reasons.append(f"Risk score {payload.risk_id} is at the LOCKDOWN band, the highest defined severity.")

    if _immediate_threat_to_life(payload):
        triggers.append(EmergencyTriggerType.IMMEDIATE_THREAT_TO_LIFE)
        reasons.append(
            f"Human exposure is confirmed while risk level is {payload.risk_level.value}, "
            "an immediate threat to life."
        )

    if _rapid_escalation(payload, previous):
        assert previous is not None  # guaranteed by _rapid_escalation's own guard
        reasons.append(
            f"Risk escalated rapidly: {previous.risk_level.value} (score {previous.score:.0f}) "
            f"-> {payload.risk_level.value} (score {payload.score:.0f})."
        )
        triggers.append(EmergencyTriggerType.RAPID_ESCALATION)

    if _cross_zone_propagation(payload):
        triggers.append(EmergencyTriggerType.CROSS_ZONE_PROPAGATION)
        zones = ", ".join(payload.affected_zones) if payload.affected_zones else "additional zones"
        paths = ", ".join(payload.propagation_paths) if payload.propagation_paths else "an identified path"
        reasons.append(f"A propagation path ({paths}) connects this event to {zones}.")

    if payload.cascade_paths:
        triggers.append(EmergencyTriggerType.CASCADE_DETECTED)
        reasons.append(f"A cascade path was detected: {' | '.join(payload.cascade_paths)}.")

    if _multiple_hazards(payload):
        triggers.append(EmergencyTriggerType.MULTIPLE_HAZARDS)
        reasons.append(
            f"{len(payload.compound_rules_fired)} compound risk rules fired simultaneously, "
            "indicating interacting hazards rather than a single isolated condition."
        )

    if _critical_control_failure(payload):
        triggers.append(EmergencyTriggerType.CRITICAL_CONTROL_FAILURE)
        controls = ", ".join(payload.critical_controls_unavailable)
        reasons.append(
            f"Critical safety control(s) unavailable ({controls}) while risk level is "
            f"{payload.risk_level.value}."
        )

    return EmergencyDecision(emergency_triggered=bool(triggers), triggers=triggers, reasons=reasons)


def _is_high_risk_band(risk_level: RiskScoreLevel) -> bool:
    return _BAND_RANK[risk_level] >= _HIGH_RISK_MIN_RANK


def _immediate_threat_to_life(payload) -> bool:
    """SS4.A. Confirmed human exposure is the one signal this schema
    carries directly; the master prompt's fuller list (fire, explosion
    risk, toxic gas, etc.) is Risk Orchestrator's job to have already
    folded into risk_level/compound_rules_fired before this agent ever
    sees the score (SS2: this agent does not recalculate domain risk)."""
    return bool(payload.human_exposure_confirmed) and _is_high_risk_band(payload.risk_level)


def _rapid_escalation(payload, previous: PreviousRisk | None) -> bool:
    """SS4.B. Requires a previous observation for this zone -- with none,
    velocity is simply unknown, not zero (the first RiskScore ever seen
    for a zone cannot be 'rapidly escalating')."""
    if previous is None:
        return False
    score_jump = payload.score - previous.score
    band_jump = _BAND_RANK[payload.risk_level] - _BAND_RANK[previous.risk_level]
    return score_jump >= RAPID_ESCALATION_SCORE_DELTA or band_jump >= RAPID_ESCALATION_MIN_BAND_JUMP


def _cross_zone_propagation(payload) -> bool:
    """SS4.C. Either an explicit propagation edge or more than one affected
    zone counts -- SS4.C's own example shows the Response Agent must NOT
    evaluate zones in isolation once more than one is implicated."""
    return bool(payload.propagation_paths) or len(payload.affected_zones) > 1


def _multiple_hazards(payload) -> bool:
    """SS4.E. HONEST LIMITATION: RiskScoreV1 does not carry a typed list of
    distinct hazard categories (e.g. 'fire' + 'chemical_release' +
    'worker_exposure') -- only compound_rules_fired (rule_ids of any
    CompoundRule that fired) and contributing_agent_result_ids (opaque
    upstream result references). Counting fired compound rules is the best
    available proxy for 'more than one hazard condition interacting' with
    the fields this contract actually has; it is NOT a semantic guarantee
    that the rules concern genuinely different hazard types. A real fix
    would give RiskScorePayload a typed hazard_categories field -- flagged
    here rather than silently treated as solved.
    """
    return len(payload.compound_rules_fired) >= MULTIPLE_HAZARDS_MIN_COMPOUND_RULES


def _critical_control_failure(payload) -> bool:
    """SS4.F. A control failure alone (e.g. at LOW risk) is not an
    emergency by itself -- SS4.F is explicit that the COMBINATION of
    hazard + failed control matters, not the control failure in isolation."""
    return bool(payload.critical_controls_unavailable) and _is_high_risk_band(payload.risk_level)
