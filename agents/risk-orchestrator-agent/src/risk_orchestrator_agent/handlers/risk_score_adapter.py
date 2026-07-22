"""handlers/risk_score_adapter.py -- the Orchestrator -> Response Agent seam.

Phase 1 integration prompt §2 ("Connect the Response Agent to the
Orchestrator"): the Orchestrator and the existing Response Agent were
built against two different models (`SystemRiskAssessment` vs
`RiskScoreV1`). This module is the "small explicit adapter" that prompt
asks for -- it does not recompute anything `SystemRiskAssessment` already
decided, it only re-shapes it into the wire contract `response_agent`
already consumes.

Nothing here duplicates risk calculation. Every value below is read
directly off `SystemRiskAssessment` / `GlobalRiskScore` / `PropagationStep`
-- this module has no rule of its own for what the risk *is*, only for how
to name it in `RiskScoreV1`'s vocabulary.

What is preserved, and where it lands (Phase 1 §2's explicit checklist):

  assessment_id        -> payload.risk_id
  event_id              -> causation_id (the event that triggered this
                           assessment; RiskScoreV1.event_id is this
                           publication's own identity, minted fresh)
  correlation_id         -> correlation_id
  site_id                -> site_id
  zone_id (primary zone)  -> zone_id / partition_key
  affected zones          -> payload.affected_zones (primary zone + every
                             zone reachable via a PropagationStep)
  global score            -> payload.score
  local / interaction score -> folded into `explanation.reasoning_steps`
                                (RiskScoreV1 has no separate local/
                                interaction fields -- seeing the numbers in
                                the explanation is preserving them, not
                                dropping them; see module docstring's
                                honesty note below)
  severity                -> payload.risk_level (mapped, see
                              _RISK_LEVEL_TO_SCORE_LEVEL)
  decision_category        -> payload.decision_category (verbatim string)
  confidence                -> explanation.confidence.value
  contributing_factors       -> payload.compound_rules_fired
  propagation_paths           -> payload.propagation_paths ("A->B" strings)
                                  and, where a path chains more than one
                                  hop from the primary zone, also folded
                                  into payload.cascade_paths
  explanation                 -> explanation.summary
  escalation_required           -> payload.escalation_required
  manual_review_required         -> payload.manual_review_required
  analysis_completeness            -> payload.analysis_completeness
  missing_domains                   -> payload.missing_domains

HONEST LIMITATION: `RiskScorePayload` has no separate `local_score`/
`interaction_score` fields of its own (only the single `score`). Rather
than either (a) silently dropping the breakdown, or (b) inventing new
wire fields for a decomposition `response_agent`'s domain logic has no use
for today, both numbers are written into `explanation.reasoning_steps` in
full, machine-parseable-if-needed text -- visible to any human or future
consumer reading the explanation, never lost. A real fix, if a future
consumer needs to branch on local vs. interaction score specifically,
would add typed fields the same way `affected_zones` etc. were added in
this same task; flagged here rather than worked around.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.risk_score_v1 import RiskScoreLevel, RiskScorePayload, RiskScoreV1

from risk_orchestrator_agent.domain.enums.risk import RiskLevel
from risk_orchestrator_agent.domain.models.system_risk_assessment import SystemRiskAssessment

PRODUCER_SERVICE = "risk_orchestrator_agent"
PRODUCER_VERSION = "0.1.0"

# RiskScoreLevel has five bands; RiskLevel (the Orchestrator's own,
# platform-wide taxonomy) has six. NEGLIGIBLE and LOW both map to
# RiskScoreLevel.LOW rather than inventing a sixth wire-level value --
# response_agent's emergency/response logic only distinguishes "below
# HIGH" from the bands above it, so this collapse loses no decision-
# relevant information (see emergency_evaluator._is_high_risk_band).
_RISK_LEVEL_TO_SCORE_LEVEL: dict[RiskLevel, RiskScoreLevel] = {
    RiskLevel.NEGLIGIBLE: RiskScoreLevel.LOW,
    RiskLevel.LOW: RiskScoreLevel.LOW,
    RiskLevel.MODERATE: RiskScoreLevel.MEDIUM,
    RiskLevel.HIGH: RiskScoreLevel.HIGH,
    RiskLevel.CRITICAL: RiskScoreLevel.CRITICAL,
    RiskLevel.CATASTROPHIC: RiskScoreLevel.LOCKDOWN,
}

# A stable namespace for coercing the Orchestrator's plain `str` ids
# (AgentResultDTO.event_id/correlation_id are opaque strings, not
# necessarily UUIDs -- see dto/agent_result_dto.py) into the UUID type
# RiskScoreV1 requires. uuid5 is deterministic: the same input string
# always produces the same UUID, so this never breaks correlation across
# retries/duplicate deliveries.
_ID_NAMESPACE = uuid.UUID("6f6a1e2a-6b1f-4b8a-9b0a-9b6b6b6b6b6b")


def _coerce_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(_ID_NAMESPACE, str(value))


def _affected_zones(assessment: SystemRiskAssessment) -> list[str]:
    zones: list[str] = [assessment.zone_id]
    for step in assessment.propagation_paths:
        for zone in (step.from_zone_id, step.to_zone_id):
            if zone and zone not in zones:
                zones.append(zone)
    return zones


def _propagation_and_cascade_paths(assessment: SystemRiskAssessment) -> tuple[list[str], list[str]]:
    """RiskScorePayload's documented string formats: propagation_paths is
    a flat list of single-hop 'from->to' edges; cascade_paths is a list of
    full multi-hop chains ('a->b->c'), earliest node first (see
    response_agent's action_planner.py SS18). `SystemRiskAssessment`
    itself only carries single-hop `PropagationStep`s -- chains are
    reconstructed here by following from_zone_id -> to_zone_id links
    starting from the primary zone, without inventing any hop the
    Orchestrator didn't already report."""
    edges = {(s.from_zone_id, s.to_zone_id) for s in assessment.propagation_paths}
    propagation_paths = [f"{a}->{b}" for a, b in edges]

    cascade_paths: list[str] = []
    by_source: dict[str, list[str]] = {}
    for a, b in edges:
        by_source.setdefault(a, []).append(b)

    def _walk(node: str, chain: list[str], visited: set[str]) -> None:
        nexts = by_source.get(node, [])
        if not nexts:
            if len(chain) > 2:
                cascade_paths.append("->".join(chain))
            return
        for nxt in nexts:
            if nxt in visited:
                continue
            _walk(nxt, [*chain, nxt], visited | {nxt})

    if assessment.zone_id in by_source:
        _walk(assessment.zone_id, [assessment.zone_id], {assessment.zone_id})

    return propagation_paths, cascade_paths


def to_risk_score_v1(assessment: SystemRiskAssessment) -> RiskScoreV1:
    """The adapter Phase 1 §2 asks for. Pure function: no I/O, no
    randomness beyond minting this publication's own `event_id` (the
    assessment's own identity is preserved as `payload.risk_id` and as
    `causation_id`, so this fresh id never loses traceability)."""
    now = datetime.now(timezone.utc)
    score_level = _RISK_LEVEL_TO_SCORE_LEVEL[assessment.severity]
    propagation_paths, cascade_paths = _propagation_and_cascade_paths(assessment)
    affected_zones = _affected_zones(assessment)

    reasoning_steps = [
        assessment.explanation,
        f"Local risk score: {assessment.global_score.local.score:.1f} "
        f"(zone {assessment.global_score.local.zone_id}, "
        f"partial_weighting={assessment.global_score.local.partial_weighting}).",
        f"Interaction (cross-zone) risk score: {assessment.global_score.interaction.score:.1f}.",
        f"Global system risk score: {assessment.global_score.value:.1f}.",
    ]
    if assessment.risk_level_changed:
        reasoning_steps.append(
            f"Severity changed from {assessment.previous_severity} to {assessment.severity.value}."
        )

    payload = RiskScorePayload(
        risk_id=assessment.assessment_id,
        score=assessment.global_score.value,
        risk_level=score_level,
        contributing_agent_result_ids=[],
        compound_rules_fired=list(assessment.contributing_factors),
        valid_until=now + timedelta(minutes=15),
        affected_zones=affected_zones,
        affected_assets=[],
        human_exposure_confirmed=False,  # not yet a typed SystemRiskAssessment field -- see class docstring gap note
        critical_controls_unavailable=[],  # ditto
        propagation_paths=propagation_paths,
        cascade_paths=cascade_paths,
        decision_category=assessment.decision_category.value,
        escalation_required=assessment.escalation_required,
        manual_review_required=assessment.manual_review_required,
        analysis_completeness=assessment.analysis_completeness,
        missing_domains=list(assessment.missing_domains),
    )

    explanation = ExplanationObject(
        summary=assessment.explanation,
        confidence=ConfidenceScore(
            value=assessment.confidence, derivation=ConfidenceDerivation.COMPOSITE,
            rule_id="risk_orchestrator_decision_engine", rule_version=1,
        ),
        evidence=[],
        reasoning_steps=reasoning_steps,
        risk_contributors=[],
        generated_at=now,
    )

    return RiskScoreV1(
        event_id=uuid.uuid4(),
        event_timestamp=now,
        correlation_id=_coerce_uuid(assessment.correlation_id),
        causation_id=_coerce_uuid(assessment.event_id),
        producer_service=PRODUCER_SERVICE,
        producer_version=PRODUCER_VERSION,
        site_id=assessment.site_id,
        zone_id=assessment.zone_id,
        partition_key=assessment.zone_id or assessment.site_id,
        trace_id=assessment.assessment_id,
        metadata=Metadata(schema_id=0, schema_version=1, environment=Environment.DEV),
        explanation=explanation,
        payload=payload,
    )
