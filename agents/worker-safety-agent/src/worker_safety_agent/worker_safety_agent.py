"""
worker_safety_agent.py

Real business logic (not a stub), scoped to the PPE responsibility named
explicitly in this agent's contracts/agent-registry/agents.yaml entry
("Human safety monitoring -- PPE, location, biometrics").

process() consumes WorkerEventV1 (sentinel_contracts.events.worker_event_v1
-- the actual generated model, not the older, structurally different draft
at contracts/events/v1/worker_event.schema.json; see README.md's
"Contract-source conflict" note for why these two disagree and which one
this agent follows and why), evaluates PPE compliance for PPE_STATUS
events via ppe_compliance_service, and now builds and returns a real
WorkerAnalysisV1 (contracts/agent-contracts/v1/WorkerAnalysis.avsc).

Previously this always returned None. That was because of two confirmed
gaps, both now closed:

  1. No generated Pydantic model existed for WorkerAnalysis anywhere in
     sentinel_contracts/. Fixed: sentinel_contracts.agent_contracts.
     worker_analysis_v1.WorkerAnalysisV1 now exists, hand-mirrored
     field-for-field from WorkerAnalysis.avsc (same convention already
     used for PermitAnalysisV1 / EnvironmentAnalysisV1). No field was
     invented.
  2. sentinel_eventbus.schema_provider.LocalSchemaProvider._preload() used
     to only load contracts/events/** schemas, never contracts/agent-
     contracts/**, so even a correct WorkerAnalysisV1 instance could not
     have been published. Fixed separately (schema_provider.py now also
     calls list_agent_contract_schemas()) -- confirmed by re-reading that
     file directly, and by rerunning tests/integration/
     test_worker_analysis_publish_gap.py, whose original premise no longer
     holds (two of its three assertions now fail because the gap they
     test for is gone; that test itself still needs updating separately,
     see README.md).

WorkerAnalysis.payload requires worker_id, risk_score, confidence, and
safety_status (all non-nullable). ppe_compliance_service's own
`.to_worker_analysis_payload_fragment()` deliberately supplies only
`ppe_compliance` and `ppe_violations` -- by that method's own docstring,
it refuses to fill fields it has "no basis to fill." risk_score,
confidence, and safety_status are now computed explicitly in
_build_worker_analysis() below, directly from ppe_compliance_score and
ppe_violations (i.e. from the same real, already-computed evaluation --
no new detection logic, no fabricated data). The exact formulas and
thresholds are a documented judgment call, called out where they're
applied, and are the natural next thing to tune once the Risk
Orchestrator's expectations for this scale are known. zone_clearance and
proximity_alerts are left at their nullable/empty defaults because this
agent has no zone-authorization or proximity/biometric signal to report
for PPE_STATUS events -- populating them would be fabrication.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from sentinel_agent_sdk import BaseAgent
from sentinel_contracts.agent_contracts.worker_analysis_v1 import (
    WorkerAnalysisPayload, WorkerAnalysisV1, WorkerSafetyStatus,
)
from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.worker_event_v1 import WorkerEventKind, WorkerEventV1

from ppe_compliance_service import PPEComplianceResult, evaluate_ppe_compliance
from zone_ppe_requirements import ZonePPERequirements

AGENT_NAME = "worker_safety_agent"
AGENT_VERSION = "0.2.0"  # bumped: now publishes real WorkerAnalysisV1, not None


class WorkerSafetyAgent(BaseAgent):
    def __init__(self, zone_ppe_requirements: ZonePPERequirements | None = None):
        self._zone_ppe_requirements = zone_ppe_requirements or ZonePPERequirements()
        # Last computed result per worker_id, kept in-process only (NOT
        # published, NOT persisted to Redis/Postgres) so tests and the demo
        # script can inspect what the agent concluded without needing a
        # publishable WorkerAnalysis to read it back from Kafka. Cleared on
        # shutdown(); this is scaffolding for the gap above, not a state
        # store this agent's design otherwise calls for.
        self.last_results: dict[str, PPEComplianceResult] = {}

    def process(self, event: BaseModel) -> BaseModel | list[BaseModel] | None:
        if not isinstance(event, WorkerEventV1):
            # AgentRunner's model_registry / EVENT_TYPES wiring (main.py)
            # should never hand this agent anything else, but process()
            # documents its own precondition rather than trusting the
            # caller silently.
            self.logger.warning("unexpected event type", event_type=type(event).__name__)
            return None

        if event.payload.event_kind != WorkerEventKind.PPE_STATUS:
            # ZONE_ENTRY / ZONE_EXIT / BIOMETRIC_ALERT are in this agent's
            # registered scope ("location, biometrics") but are NOT part of
            # the PPE responsibility this implementation pass covers -- left
            # unhandled here rather than guessed at, matching the master
            # prompt's "no assumptions" rule. Not a gap: simply out of
            # scope for this change.
            return None

        return self._handle_ppe_status(event)

    def _handle_ppe_status(self, event: WorkerEventV1) -> WorkerAnalysisV1:
        required_ppe = self._zone_ppe_requirements.required_for(event.zone_id)
        result = evaluate_ppe_compliance(
            worker_id=event.payload.worker_id,
            zone_id=event.zone_id,
            detected_ppe=event.payload.ppe_status,
            required_ppe=required_ppe,
        )
        self.last_results[event.payload.worker_id] = result

        self.logger.info(
            "ppe compliance evaluated",
            worker_id=result.worker_id,
            zone_id=result.zone_id,
            site_id=event.site_id,
            required_ppe=result.required_ppe,
            detected_ppe=result.detected_ppe,
            ppe_compliance=result.ppe_compliance_score,
            ppe_violations=result.ppe_violations,
            unknown_ppe_keys=result.unknown_ppe_keys,
            causation_event_id=str(event.event_id),
        )
        return self._build_worker_analysis(event, result)

    def _build_worker_analysis(self, event: WorkerEventV1, result: PPEComplianceResult) -> WorkerAnalysisV1:
        """Maps a real PPEComplianceResult onto the existing WorkerAnalysis
        contract. Two fields (ppe_compliance, ppe_violations) come straight
        from the compliance service via .to_worker_analysis_payload_fragment().
        risk_score, confidence, and safety_status are payload fields the
        contract requires (non-nullable in WorkerAnalysis.avsc) that the
        compliance service itself declines to fill -- computed here from the
        SAME real evaluation, not from new detection logic or invented data:

          risk_score (contract range [0, 100], matching Permit/Environment
          Analysis's identical scale) = (1 - ppe_compliance_score) * 100.
          Fully compliant -> 0; fully non-compliant -> 100.

          confidence (contract range [0, 1]) = 1.0 when this zone actually
          has PPE requirements to check against; 0.5 when required_ppe is
          empty, since a "safe" conclusion drawn from nothing being required
          carries less information than one drawn from an actual check.
          This is a judgment call, called out explicitly rather than
          buried -- revisit once the Orchestrator's expectations for this
          field are known.

          safety_status: `safe` at full compliance, `in_danger` when fewer
          than half of required items are present, `at_risk` otherwise.
          `unresponsive` is never assigned here -- PPE_STATUS events carry
          no biometric signal, so this agent has no basis to claim it.

        zone_clearance and proximity_alerts are left at their nullable/
        empty defaults: this agent performs no zone-authorization or
        proximity check, so populating them would be fabrication.
        """
        now = datetime.now(timezone.utc)
        fragment = result.to_worker_analysis_payload_fragment()

        if not result.required_ppe:
            confidence = 0.5
        else:
            confidence = 1.0
        risk_score = round((1.0 - result.ppe_compliance_score) * 100, 2)

        if result.ppe_compliance_score >= 1.0:
            safety_status = WorkerSafetyStatus.safe
        elif result.ppe_compliance_score < 0.5:
            safety_status = WorkerSafetyStatus.in_danger
        else:
            safety_status = WorkerSafetyStatus.at_risk

        violations_str = ", ".join(result.ppe_violations)
        evidence = [
            f"{item}: {'present' if event.payload.ppe_status and event.payload.ppe_status.get(item) else 'MISSING'}"
            for item in result.required_ppe
        ]
        if result.unknown_ppe_keys:
            evidence.append(f"additional PPE detected but not required in this zone: {', '.join(result.unknown_ppe_keys)}")
        recommendations = [
            f"Worker {result.worker_id} must put on {item} before continuing work in zone {result.zone_id}."
            for item in result.ppe_violations
        ]

        return WorkerAnalysisV1(
            event_id=uuid.uuid4(),
            event_timestamp=now,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            producer_service=AGENT_NAME,
            producer_version=AGENT_VERSION,
            site_id=event.site_id,
            zone_id=event.zone_id,
            partition_key=event.zone_id,
            trace_id=getattr(event, "trace_id", None),
            metadata=Metadata(schema_id=1, schema_version=1, environment=Environment.DEV),
            agent_id=AGENT_NAME,
            agent_version=AGENT_VERSION,
            input_events=[event.event_id],
            confidence=confidence,
            processing_time_ms=0,
            explanation=ExplanationObject(
                summary=(
                    f"Worker {result.worker_id} is "
                    f"{'fully PPE-compliant' if result.is_fully_compliant else 'missing required PPE: ' + violations_str} "
                    f"in zone {result.zone_id}."
                ),
                confidence=ConfidenceScore(value=confidence, derivation=ConfidenceDerivation.RULE_BASED),
                evidence=[],
                reasoning_steps=[],
                generated_at=now,
            ),
            payload=WorkerAnalysisPayload(
                worker_id=result.worker_id,
                risk_score=risk_score,
                confidence=confidence,
                safety_status=safety_status,
                ppe_compliance=fragment["ppe_compliance"],
                ppe_violations=fragment["ppe_violations"],
                zone_clearance=None,
                proximity_alerts=[],
                evidence=evidence,
                recommendations=recommendations,
                analyzed_at=now,
            ),
        )
