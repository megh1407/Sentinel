"""
zone_compatibility_evaluator.py

Phase 2C / Phase 3 of the integration master prompt: compare the permit's
target zone against the current ZoneState (NOT ZoneAnalysis -- see
README's "PLATFORM_GAP: ZoneAnalysis" note; sentinel.zone.analysis.v1 has
no real producer anywhere in this repo, confirmed directly in
agents/zone_intelligence_agent/main.py's own PLATFORM_GAP comments, so
Permit Agent cannot depend on it despite agents.yaml listing it).

Elevated-risk permit types (operations that create or interact with an
ignition/energy source) are treated more conservatively than routine ones.
This mapping is an operational default, not itself part of any frozen
contract -- it should be reviewed by the safety domain owner before this
agent is trusted in production. It intentionally mirrors the master
prompt's own worked example: HOT_WORK + HIGH GAS HAZARD -> HIGH CONFLICT.
"""
from __future__ import annotations

from permit_intelligence_agent.models.permit_finding import Evaluability
from sentinel_contracts.events.permit_event_v1 import PermitType
from sentinel_contracts.events.zone_state_v1 import RiskLevel, ZoneStateV1

ELEVATED_RISK_PERMIT_TYPES = frozenset({PermitType.HOT_WORK, PermitType.CONFINED_SPACE, PermitType.ELECTRICAL})

# zone risk level -> (blocks ALL permits, blocks elevated-risk permits only)
_ZONE_BLOCK_RULES: dict[RiskLevel, tuple[bool, bool]] = {
    RiskLevel.LOCKDOWN: (True, True),
    RiskLevel.CRITICAL: (False, True),
    RiskLevel.HIGH: (False, False),  # warning-level only, not blocking -- see evaluate()
    RiskLevel.MEDIUM: (False, False),
    RiskLevel.LOW: (False, False),
}


class ZoneCompatibilityEvaluator:
    def evaluate(
        self, permit_type: PermitType, zone_state: ZoneStateV1 | None
    ) -> tuple[bool | None, float | None, list[str], dict[str, str]]:
        """Returns (zone_compatibility, zone_risk_at_issuance, findings, evaluability).
        zone_compatibility=None means UNKNOWN -- callers must never treat
        that as "safe" (Phase 3: 'Never assume: No ZoneState = Safe')."""
        findings: list[str] = []

        if zone_state is None:
            return None, None, ["ZONE_CONTEXT_UNAVAILABLE: no ZoneState cached for this zone_id"], {
                "zone_compatibility_check": Evaluability.UNKNOWN.value,
            }

        risk_level = zone_state.payload.current_risk_level
        risk_score = _RISK_LEVEL_SCORE[risk_level]
        block_all, block_elevated = _ZONE_BLOCK_RULES[risk_level]
        is_elevated_permit = permit_type in ELEVATED_RISK_PERMIT_TYPES

        compatible = True
        if block_all:
            compatible = False
            findings.append(f"ZONE_LOCKDOWN: zone risk level is {risk_level.value}; no permit is compatible")
        elif block_elevated and is_elevated_permit:
            compatible = False
            findings.append(
                f"ZONE_RISK_BLOCKS_PERMIT_TYPE: {permit_type.value} is not compatible with "
                f"zone risk level {risk_level.value}"
            )
        elif risk_level == RiskLevel.HIGH and is_elevated_permit:
            # Not outright blocking, but flagged -- matches the master
            # prompt's worked example (HOT_WORK + HIGH GAS HAZARD -> HIGH
            # CONFLICT, "flagged or blocked according to contract semantics").
            findings.append(
                f"ZONE_RISK_ELEVATED_FOR_PERMIT_TYPE: {permit_type.value} during zone risk level "
                f"{risk_level.value} warrants review"
            )

        if zone_state.payload.is_stale:
            findings.append("ZONE_CONTEXT_STALE: cached ZoneState is marked stale by its producer")

        return compatible, risk_score, findings, {"zone_compatibility_check": Evaluability.EVALUATED.value}


_RISK_LEVEL_SCORE: dict[RiskLevel, float] = {
    RiskLevel.LOW: 10.0,
    RiskLevel.MEDIUM: 35.0,
    RiskLevel.HIGH: 65.0,
    RiskLevel.CRITICAL: 90.0,
    RiskLevel.LOCKDOWN: 100.0,
}
