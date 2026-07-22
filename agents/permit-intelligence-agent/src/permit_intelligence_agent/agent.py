"""
agent.py

PermitIntelligenceAgent -- the BaseAgent subclass. Per sentinel_agent_sdk's
design, this implements exactly process(); AgentRunner (main.py) owns
consuming, publishing, retries, metrics, and shutdown.

Boundary (verified against contracts/agent-registry/agents.yaml AND actual
producer code, not just the registry -- see README.md):

  consumes:
    - PermitEventV1  (sentinel.permit.events.v1)   -- real, canonical
    - ZoneStateV1    (sentinel.zone.state.v1)       -- real, canonical
  NOT consumed, despite being listed in agents.yaml's `consumes`:
    - ZoneAnalysis (sentinel.zone.analysis.v1) -- no real producer anywhere
      in the repo (zone_intelligence_agent's own main.py documents this gap
      on its publish side; this agent inherits the same gap on the consume
      side). See README.

  produces:
    - PermitAnalysisV1 (contracts/agent-contracts/v1/PermitAnalysis.avsc,
      sentinel_contracts.agent_contracts.permit_analysis_v1.PermitAnalysisV1)
      to sentinel.permit.analysis.v1. This schema and generated model did
      not exist before this task -- added following the exact convention
      already established by ZoneAnalysis.avsc / EnvironmentAnalysis.avsc /
      WorkerAnalysis.avsc / MaintenanceAnalysis.avsc / IncidentAnalysis.avsc,
      mechanically translated from the pre-existing, frozen
      permit_analysis.schema.json (see PermitAnalysis_field_mapping.md).
      No unrelated contract was touched to make this possible.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sentinel_agent_sdk import BaseAgent
from sentinel_common.errors import ContractViolationError
from sentinel_contracts.agent_contracts.permit_analysis_v1 import (
    PermitAnalysisPayload, PermitAnalysisV1, PermitConflictDetail as WirePermitConflictDetail,
    PermitConflictSeverity as WirePermitConflictSeverity, PermitRiskLevel,
)
from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.evidence_item import EvidenceItem
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.permit_event_v1 import PermitEventV1
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

from permit_intelligence_agent.models.permit_finding import PermitFinding
from permit_intelligence_agent.services.permit_analysis_builder import PermitAnalysisBuilder

AGENT_NAME = "permit_intelligence_agent"
AGENT_VERSION = "0.2.0"  # bumped: now publishes the real PermitAnalysisV1 contract, not the AgentResultV1 interim path
ZONE_CONTEXT_TTL_SECONDS = 300
DEDUPE_TTL_SECONDS = 24 * 3600


class PermitIntelligenceAgent(BaseAgent):
    def initialize(self) -> None:
        self._builder = PermitAnalysisBuilder()

    # -- BaseAgent contract: the one method every agent implements --
    def process(self, event: BaseModel):
        if isinstance(event, ZoneStateV1):
            return self._process_zone_state(event)
        if isinstance(event, PermitEventV1):
            return self._process_permit_event(event)
        raise ContractViolationError(f"PermitIntelligenceAgent received an unexpected event type: {type(event).__name__}")

    # -- ZoneState half of the boundary: cache latest context by zone_id --
    def _process_zone_state(self, event: ZoneStateV1) -> None:
        if self.state.zone is not None:
            self.state.zone.set(event.zone_id, event, ttl_seconds=ZONE_CONTEXT_TTL_SECONDS)
            self.logger.info("zone context cached", zone_id=event.zone_id, risk_level=event.payload.current_risk_level.value)
        else:
            self.logger.warning("no redis-backed zone state repository configured -- zone context caching disabled")
        return None  # ZoneState never produces a permit-facing result on its own (Scenario G handles re-evaluation below)

    # -- PermitEvent half of the boundary: the actual analysis pipeline --
    def _process_permit_event(self, event: PermitEventV1) -> PermitAnalysisV1 | None:
        started = datetime.now(timezone.utc)
        if self._is_duplicate(event):
            self.logger.info("duplicate PermitEvent ignored", event_id=str(event.event_id))
            return None

        zone_state = self._load_zone_context(event.zone_id)
        if zone_state is None:
            self.logger.warning(
                "no ZoneState cached for zone -- proceeding with zone_compatibility=UNKNOWN, not assumed-safe",
                zone_id=event.zone_id,
            )

        finding = self._builder.build(event, zone_state)
        self.logger.info(
            "permit analyzed", permit_id=finding.permit_id, risk_level=finding.permit_risk_level,
            risk_score=finding.risk_score, confidence=finding.confidence,
        )
        processing_time_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return self._build_permit_analysis(event, zone_state, finding, processing_time_ms)

    # -- idempotency (duplicate PermitEvent must not double-process) --
    def _is_duplicate(self, event: PermitEventV1) -> bool:
        redis_client = self.container.state.redis_client
        if redis_client is None:
            return False  # no backend configured -- fail open, matches StateContainer's graceful-degradation design
        key = f"permit_agent:seen_event:{event.event_id}"
        was_new = redis_client.set(key, "1", nx=True, ex=DEDUPE_TTL_SECONDS)
        return not bool(was_new)

    def _load_zone_context(self, zone_id: str) -> ZoneStateV1 | None:
        if self.state.zone is None:
            return None
        return self.state.zone.get(zone_id, ZoneStateV1)

    # -- build the real, canonical PermitAnalysisV1 --
    def _build_permit_analysis(
        self, source_event: PermitEventV1, zone_state: ZoneStateV1 | None, finding: PermitFinding, processing_time_ms: int,
    ) -> PermitAnalysisV1:
        summary = (
            f"Permit {finding.permit_id}: {finding.permit_risk_level.upper()} risk "
            f"(score {finding.risk_score:.0f}/100, {len(finding.conflicts)} conflict(s))."
        )
        evidence_items = [EvidenceItem(
            source_event_id=str(source_event.event_id),
            source_type="PermitEvent",
            description="Source permit event that triggered this analysis.",
            weight=1.0,
            timestamp=source_event.event_timestamp,
        )]
        if zone_state is not None:
            evidence_items.append(EvidenceItem(
                source_event_id=str(zone_state.event_id),
                source_type="ZoneState",
                description=f"Zone context used for compatibility evaluation (risk level: {zone_state.payload.current_risk_level.value}).",
                weight=1.0,
                timestamp=zone_state.event_timestamp,
            ))

        wire_conflicts = [
            WirePermitConflictDetail(
                conflicting_permit_id=c.conflicting_permit_id, conflict_type=c.conflict_type,
                severity=WirePermitConflictSeverity(c.severity),
            )
            for c in finding.conflicts
        ]

        payload = PermitAnalysisPayload(
            permit_id=finding.permit_id,
            permit_risk_level=PermitRiskLevel(finding.permit_risk_level),
            risk_score=finding.risk_score,
            confidence=finding.confidence,
            conflicts=wire_conflicts,
            zone_compatibility=finding.zone_compatibility,  # None == UNKNOWN, carried through untouched
            zone_risk_at_issuance=finding.zone_risk_at_issuance,
            evidence=finding.evidence,
            recommendations=finding.recommendations,
            analyzed_at=finding.analyzed_at,
        )

        return PermitAnalysisV1(
            event_id=uuid.uuid4(),
            event_timestamp=datetime.now(timezone.utc),
            correlation_id=source_event.correlation_id,
            causation_id=source_event.event_id,
            producer_service=AGENT_NAME,
            producer_version=AGENT_VERSION,
            site_id=source_event.site_id,
            zone_id=source_event.zone_id,
            partition_key=source_event.zone_id,
            metadata=Metadata(schema_id=0, schema_version=1, environment=Environment.DEV),
            agent_id=AGENT_NAME,
            agent_version=AGENT_VERSION,
            input_events=[source_event.event_id] + ([zone_state.event_id] if zone_state is not None else []),
            confidence=finding.confidence,
            processing_time_ms=processing_time_ms,
            explanation=ExplanationObject(
                summary=summary,
                confidence=ConfidenceScore(
                    value=finding.confidence, derivation=ConfidenceDerivation.RULE_BASED,
                    rule_id="permit_zone_compatibility_v1", rule_version=1,
                ),
                evidence=evidence_items,
                reasoning_steps=finding.findings or ["No rule findings -- permit evaluated as nominal."],
                risk_contributors=[],
                rule_metadata={  # kept for per-check evaluability transparency (BLOCKED_BY_INPUT_CONTRACT etc.) --
                    # not a substitute for the now-typed payload fields above, just the "why" behind them
                    "rule_id": "permit_zone_compatibility_v1", "rule_version": "1", **finding.evaluability,
                },
                generated_at=finding.analyzed_at,
            ),
            payload=payload,
        )
