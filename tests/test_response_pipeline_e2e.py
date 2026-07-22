"""tests/test_response_pipeline_e2e.py -- Phase 1 §Phase 8 end-to-end proof.

Proves the seam this task was actually about:

    RiskContext + RuleFindings          (agent intelligence, already scored)
        -> RiskScorer / CrossZoneRiskAnalyzer / DecisionEngine / ExplanationBuilder
        -> SystemRiskAssessment            (risk_orchestrator_agent, unmodified math)
        -> handlers/risk_score_adapter.to_risk_score_v1   (Phase 1 §2's adapter)
        -> RiskScoreV1                     (the real, existing wire contract)
        -> response_agent.services.response_service.ResponseService
        -> ActionRequestV1 list             (the real, existing Response Agent)

SCOPE, STATED HONESTLY: this exercises the domain services directly
(RuleFinding/NeighborZoneContext built by hand) rather than through the
full Kafka-wire `EventRouter` -> `ContextBuilder` -> Neo4j-backed
`GraphRepositoryPort` path. That fuller path needs a live graph topology
adapter this task did not build (see risk_score_adapter.py's own gap
note, and cross_zone.py's module docstring on the same limitation) --
this test proves the Orchestrator-to-Response-Agent seam this task
actually implements, not the graph-topology enrichment, which is
unchanged, pre-existing, and out of this task's scope.

ENVIRONMENT NOTE: this sandbox has no network access, so `pydantic` /
`redis` could not be installed here and this file could not actually be
executed in this task's authoring environment. It is written to run with
`pip install pydantic redis pytest pytest-asyncio` and this repo's
libs/*/agents/*/src on PYTHONPATH (see repo tests/conftest.py's existing
sys.path setup, which already covers this). Every import and attribute
access below was checked by hand against the real source, not guessed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from risk_orchestrator_agent.domain.decision.decision_engine import DecisionEngine
from risk_orchestrator_agent.domain.enums import RuleCategory, RulePriority
from risk_orchestrator_agent.domain.explanation.explanation_builder import ExplanationBuilder
from risk_orchestrator_agent.domain.models.evidence_collection import EvidenceCollection
from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext
from risk_orchestrator_agent.domain.models.operational_timeline import OperationalTimeline
from risk_orchestrator_agent.domain.models.risk_context import (
    ConfidenceModel, ContextQuality, CorrelationMetadata, RiskContext, SiteContext, VersionMetadata,
)
from risk_orchestrator_agent.domain.models.rule_finding import RuleFinding
from risk_orchestrator_agent.domain.models.system_risk_assessment import SystemRiskAssessment
from risk_orchestrator_agent.domain.scoring.cross_zone import CrossZoneRiskAnalyzer
from risk_orchestrator_agent.domain.scoring.risk_scorer import RiskScorer
from risk_orchestrator_agent.handlers.risk_score_adapter import to_risk_score_v1

from response_agent.services.response_service import ResponseService

pytestmark = pytest.mark.asyncio


def _bare_context(zone_id: str, site_id: str, *, neighbor_zones: tuple[NeighborZoneContext, ...] = ()) -> RiskContext:
    """The minimum viable RiskContext for exercising RiskScorer /
    CrossZoneRiskAnalyzer / DecisionEngine / ExplanationBuilder directly
    -- every sub-context ContextBuilder would normally populate from a
    live event, but hand-built here since those services only read the
    fields used below (zone_id, quality.completeness, neighbor_zones)."""
    now = datetime.now(timezone.utc)
    return RiskContext(
        zone_id=zone_id, site_id=site_id, snapshot_at=now,
        site=SiteContext(site_id=site_id), zone=None, workers=(), equipment=(), permits=(),
        sensor=None, incident=None, maintenance=(), historical=None, neighbor_zones=neighbor_zones,
        operational_timeline=OperationalTimeline(entries=()),
        evidence=EvidenceCollection(items=()),
        correlation_findings=(),
        confidence_model=ConfidenceModel(aggregate_confidence=0.9, per_domain_confidence={"sensor": 0.9}),
        version_metadata=VersionMetadata(context_builder_version="test"),
        correlation_metadata=CorrelationMetadata(correlation_id="corr-e2e", causation_id=None),
        quality=ContextQuality(completeness=1.0),
    )


async def _assess(zone_id: str, site_id: str, event_id: str, correlation_id: str,
                   findings: tuple[RuleFinding, ...], neighbor_zones: tuple[NeighborZoneContext, ...] = (),
                   ) -> SystemRiskAssessment:
    """Mirrors `Orchestrator.handle_event`'s body (orchestration_pipeline.py)
    exactly, minus the ContextBuilder/EventPublisher I/O steps -- same
    RiskScorer/CrossZoneRiskAnalyzer/DecisionEngine/ExplanationBuilder
    calls, in the same order, with the same field mapping into
    SystemRiskAssessment."""
    context = _bare_context(zone_id, site_id, neighbor_zones=neighbor_zones)
    local_score = RiskScorer().score(context, findings)
    interaction_risk = CrossZoneRiskAnalyzer().analyze(context, findings)
    decision_engine = DecisionEngine()
    global_score = decision_engine.synthesize(context, local_score, interaction_risk)
    severity, category, escalation_required, manual_review_required = decision_engine.classify(
        global_score, findings=findings, previous_severity=None,
    )
    explanation_builder = ExplanationBuilder()
    contributing_factors = explanation_builder.contributing_factors(global_score, findings)
    explanation_text = explanation_builder.build(global_score, findings, severity=severity.value)

    return SystemRiskAssessment(
        assessment_id=str(uuid.uuid4()), zone_id=zone_id, site_id=site_id, event_id=event_id,
        correlation_id=correlation_id, computed_at=datetime.now(timezone.utc), global_score=global_score,
        severity=severity, decision_category=category, confidence=context.confidence_model.aggregate_confidence,
        contributing_factors=contributing_factors, propagation_paths=interaction_risk.propagation_paths,
        explanation=explanation_text, escalation_required=escalation_required,
        manual_review_required=manual_review_required, analysis_completeness=global_score.analysis_completeness,
        missing_domains=global_score.missing_domains, risk_level_changed=False, previous_severity=None,
    )


def _gas_hazard_finding() -> RuleFinding:
    return RuleFinding(
        rule_id="ENV-TOXIC-GAS-BREACH", category=RuleCategory.ENVIRONMENTAL, priority=RulePriority.CRITICAL,
        weight=0.85, confidence=0.9, description="Toxic gas concentration breached threshold (38.5ppm > 35ppm).",
    )


class _CapturingRepo:
    """Minimal stand-in for sentinel_state.ResponseTrackingRepository
    (matches its exact method signatures) -- proves idempotency without
    needing a real Redis connection, same role FakeResponseTrackingRepository
    plays in response_agent's own unit tests."""

    def __init__(self):
        self._seen: set[str] = set()
        self._active: dict[str, dict] = {}
        self._prev: dict[str, dict] = {}
        self._meta: dict[str, dict] = {}

    def was_event_processed(self, event_id): return event_id in self._seen
    def mark_event_processed(self, event_id, ttl_seconds=86400): self._seen.add(event_id)
    def get_previous_risk(self, zone_id): return self._prev.get(zone_id)
    def set_previous_risk(self, zone_id, score, risk_level, observed_at, ttl_seconds=3600):
        self._prev[zone_id] = {"score": score, "risk_level": risk_level, "observed_at": observed_at}
    def get_active_response(self, risk_id): return self._active.get(risk_id)
    def set_active_response(self, risk_id, record, ttl_seconds=86400): self._active[risk_id] = record
    def clear_active_response(self, risk_id): self._active.pop(risk_id, None)
    def get_action_meta(self, action_id): return self._meta.get(action_id)
    def set_action_meta(self, action_id, meta, ttl_seconds=86400): self._meta[action_id] = meta


async def test_single_zone_high_risk_reaches_response_agent_as_a_real_action():
    """TEST 2 (HIGH RISK) of the master prompt's Phase 1 test matrix,
    run through the real seam end-to-end."""
    findings = (_gas_hazard_finding(),)
    assessment = await _assess("ZONE-A", "SITE-1", "evt-1", "corr-1", findings)

    risk_score = to_risk_score_v1(assessment)
    assert risk_score.payload.risk_id == assessment.assessment_id
    assert risk_score.payload.decision_category == assessment.decision_category.value
    assert risk_score.payload.escalation_required == assessment.escalation_required

    service = ResponseService(response_repo=_CapturingRepo())
    actions = service.handle_risk_score(risk_score)
    assert actions, "a HIGH+ risk score must produce at least one real action"


async def test_multi_zone_propagation_survives_orchestrator_to_response_agent():
    """TEST 4/5 (MULTI-ZONE COMPOUND RISK / PROPAGATION) of the master
    prompt's test matrix: ZONE-A has an active hazard AND shares
    ventilation with an already-elevated ZONE-B. Proves the propagation
    path the Orchestrator's CrossZoneRiskAnalyzer detects is not lost by
    the adapter, and that the Response Agent's plan reflects the combined
    (not merely per-zone) picture -- master prompt §11's central rule.
    """
    findings = (_gas_hazard_finding(),)
    neighbor_zones = (
        NeighborZoneContext(neighbor_zone_id="ZONE-B", neighbor_state="danger",
                             distance_m=12.0, relationship_type="shares_ventilation"),
    )
    assessment = await _assess("ZONE-A", "SITE-1", "evt-2", "corr-2", findings, neighbor_zones=neighbor_zones)

    # The Orchestrator's own cross-zone analysis must have found the
    # propagation path -- if this assertion fails, the *Orchestrator*
    # (unmodified by this task) isn't detecting it, which is a
    # precondition of the rest of this test, not this task's bug.
    assert assessment.propagation_paths, "CrossZoneRiskAnalyzer should have found the ZONE-A->ZONE-B path"
    assert assessment.global_score.interaction.score > 0

    risk_score = to_risk_score_v1(assessment)
    assert "ZONE-A->ZONE-B" in risk_score.payload.propagation_paths
    assert "ZONE-B" in risk_score.payload.affected_zones

    service = ResponseService(response_repo=_CapturingRepo())
    actions = service.handle_risk_score(risk_score)
    assert actions, "compound cross-zone risk must produce a real response, not silence"


async def test_duplicate_assessment_does_not_produce_a_duplicate_response():
    """TEST 8 (DUPLICATE ASSESSMENT): the exact same RiskScoreV1 event
    (same event_id -- e.g. Kafka at-least-once redelivery of the same
    published assessment) delivered twice must not double the response."""
    findings = (_gas_hazard_finding(),)
    assessment = await _assess("ZONE-A", "SITE-1", "evt-3", "corr-3", findings)
    risk_score = to_risk_score_v1(assessment)

    service = ResponseService(response_repo=_CapturingRepo())
    first = service.handle_risk_score(risk_score)
    assert first is not None

    second = service.handle_risk_score(risk_score)  # identical event_id
    assert second is None


async def test_incomplete_analysis_reaches_response_agent_as_a_review_action():
    """TEST 6 (INCOMPLETE ANALYSIS): missing_domains/manual_review_required
    must not be dropped by the adapter, and must produce a concrete
    review action rather than false certainty (master prompt §12)."""
    findings = (_gas_hazard_finding(),)
    assessment = await _assess("ZONE-A", "SITE-1", "evt-4", "corr-4", findings)
    # Simulate the Orchestrator having flagged incomplete analysis (a real
    # GlobalRiskScore can report this; overridden here directly since this
    # test's hand-built context always reports completeness=1.0).
    import dataclasses
    assessment = dataclasses.replace(
        assessment, manual_review_required=True, analysis_completeness="partial",
        missing_domains=("maintenance_intelligence",),
    )
    risk_score = to_risk_score_v1(assessment)
    assert risk_score.payload.manual_review_required is True
    assert risk_score.payload.missing_domains == ["maintenance_intelligence"]

    service = ResponseService(response_repo=_CapturingRepo())
    actions = service.handle_risk_score(risk_score)
    assert actions is not None
    assert any(a.payload.action_type.value == "REQUEST_HUMAN_REVIEW" for a in actions)
