"""hello_agent.py — The reference agent for SENTINEL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sentinel_agent_sdk.base_agent import BaseAgent
from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.evidence_item import EvidenceItem, EvidenceType
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.agent_result_v1 import AgentResultPayload, AgentResultV1


class HelloAgent(BaseAgent):
    """Reference implementation of a SENTINEL agent."""

    def process(self, event) -> AgentResultV1:
        event_id_str = str(event.event_id)
        if hasattr(self.state, "hello") and self.state.hello:
            self.state.hello.set_seen(event_id_str)
        if hasattr(self.state, "hello_pg") and self.state.hello_pg:
            self.state.hello_pg.set_seen(event_id_str)

        now = datetime.now(timezone.utc)
        evidence = [
            EvidenceItem(
                evidence_id=f"ev-{uuid.uuid4().hex[:8]}",
                evidence_source="hello_agent",
                evidence_type=EvidenceType.SENSOR_READING,
                confidence=1.0,
                timestamp=now,
                origin_agent="HelloAgent",
                supporting_event_ids=(event_id_str,),
            )
        ]

        explanation = ExplanationObject(
            summary="Processed hello agent event",
            confidence=ConfidenceScore(value=1.0, derivation=ConfidenceDerivation.DIRECT, rule_id="hello", rule_version=1),
            evidence=evidence,
            reasoning_steps=["Received sensor event", "Logged state"],
            risk_contributors=[],
            generated_at=now,
        )

        return AgentResultV1(
            event_id=uuid.uuid4(),
            event_timestamp=now,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            producer_service="HelloAgent",
            producer_version="1.0.0",
            site_id=event.site_id,
            zone_id=event.zone_id,
            partition_key=event.partition_key or event.site_id,
            trace_id=event.trace_id,
            metadata=Metadata(schema_id=101, schema_version=1, environment=Environment.DEV),
            explanation=explanation,
            payload=AgentResultPayload(finding="NO_FINDING", confidence=1.0),
        )
