"""
orchestrator_bridge.py

Translates real SENTINEL events (the four already-verified agents' real
output) into the raw envelope dicts risk_orchestrator_agent.dto.
agent_result_dto.AgentResultDTO.from_raw expects. This is the explicit
adapter the merge master prompt asks for (S4: "Create adapters only where
existing modules have incompatible contracts") -- it does not modify the
Orchestrator's own code, and does not modify the four agents' own code.

THREE OF FOUR translations are near-lossless -- EnvironmentAnalysisV1,
PermitAnalysisV1, and WorkerAnalysisV1 already carry almost exactly the
AgentResultDTO envelope shape (event_id, correlation_id, agent_id,
agent_version, input_events, result_type, confidence, processing_time_ms,
error, payload) because both were independently designed against the same
"AgentResult envelope" concept.

ONE translation is a REAL, DOCUMENTED GAP BRIDGE, not a clean mapping:
zone_state_to_zone_analysis_raw() below. The Orchestrator's own contract
(contracts/agent-registry/agents.yaml, handlers/consumers.py's
INBOUND_TOPICS) expects `sentinel.zone.analysis.v1` / result_type
"zone_analysis" -- but the real, live Zone Intelligence Agent (verified
earlier this session) only ever publishes `sentinel.zone.state.v1`
(ZoneStateV1). No agent anywhere in this repository produces a real
ZoneAnalysis event; the schema exists at contracts/agent-contracts/v1/
but nothing populates it (see the Environmental/Permit/Worker-Safety
agents' own main.py docstrings, all independently discovering and
mis-describing this same gap). Rather than inventing a fake producer or
leaving the Orchestrator with no zone-level input at all, this function
builds the best-effort ZoneContext the real ZoneState data actually
supports, and is explicit in its own docstring about exactly what's
faithful and what's a documented absence:

  - zone_state, worker_count: real, directly from ZoneStateV1
  - risk_factors, equipment_ids: real IDs, from active_sensor_alert_ids /
    active_equipment_risk_ids
  - anomalies: ALWAYS EMPTY. ZoneAnomalyDetected is computed by the real
    Zone Agent but never published to Kafka (no topic registered for it --
    see the Zone Agent's own main.py PLATFORM_GAP note) so there is no
    real anomaly data anywhere on the wire to carry through. Empty, not
    guessed at -- ContextBuilder/ContextQuality already treat an empty
    tuple honestly rather than as "no anomalies exist."
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _base_envelope(event: dict, *, result_type: str, agent_id: str, agent_version: str, payload: dict[str, Any]) -> dict:
    """Fields common to every translation -- pulled from the real
    envelope every SENTINEL event already carries (event_id,
    correlation_id, causation_id, site_id, zone_id, event_timestamp,
    metadata.schema_version), regardless of which agent produced it."""
    return {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "event_version": event.get("event_version", 1),
        "timestamp": event["event_timestamp"],
        "source": event.get("producer_service", agent_id),
        "site_id": event["site_id"],
        "zone_id": event["zone_id"],
        "correlation_id": event["correlation_id"],
        "causation_id": event.get("causation_id"),
        "schema_version": str(event.get("metadata", {}).get("schema_version", 1)),
        "agent_id": agent_id,
        "agent_version": agent_version,
        "input_events": tuple(event.get("input_events", ()) or ()),
        "result_type": result_type,
        "confidence": event.get("confidence", event.get("payload", {}).get("confidence", 0.5)),
        "processing_time_ms": event.get("processing_time_ms", 0),
        "error": event.get("error"),
        "payload": payload,
    }


def environment_analysis_to_raw(event: dict) -> dict:
    """EnvironmentAnalysisV1 (real, verified) -> raw envelope for
    result_type="environment_analysis" (AgentResultDTO.domain_name ->
    "sensor", per DOMAIN_BY_RESULT_TYPE).

    The Orchestrator's own domain/context/merge_rules.py's parse_sensor()
    expects payload["hazards"] as a list of dicts with hazard_type/
    measured_value/unit/threshold_ppm/threshold_breach/trend/sensor_ids --
    which is almost exactly the real HazardReading shape
    EnvironmentAnalysisV1.payload.hazards already has (both independently
    modeled the same "hazard reading" concept). Passed through directly
    rather than reshaped -- an earlier version of this function rebuilt an
    incompatible {gas_readings, hazard_types} shape here, which silently
    produced an empty SensorContext.hazards tuple every time (caught by
    running the real integration end-to-end and finding gas/temperature
    hazards never appeared in a SystemRiskAssessment's contributing_factors,
    then tracing it back to this mismatch)."""
    p = event["payload"]
    return _base_envelope(
        event,
        result_type="environment_analysis",
        agent_id=event.get("agent_id", "environmental_intelligence_agent"),
        agent_version=event.get("agent_version", "0.0.0"),
        payload={
            "hazards": p.get("hazards", []),
            "evacuation_required": p.get("evacuation_required", False),
            "affected_zones": p.get("affected_zones", []),
        },
    )


def permit_analysis_to_raw(event: dict) -> dict:
    """PermitAnalysisV1 (real, verified) -> raw envelope for
    result_type="permit_analysis"."""
    p = event["payload"]
    return _base_envelope(
        event,
        result_type="permit_analysis",
        agent_id=event.get("agent_id", "permit_intelligence_agent"),
        agent_version=event.get("agent_version", "0.0.0"),
        payload={
            "permit_id": p.get("permit_id"),
            "permit_risk_level": p.get("permit_risk_level"),
            "zone_compatibility": p.get("zone_compatibility"),
            "zone_risk_at_issuance": p.get("zone_risk_at_issuance"),
            "conflicts": p.get("conflicts", []),
        },
    )


def worker_analysis_to_raw(event: dict) -> dict:
    """WorkerAnalysisV1 (real, verified) -> raw envelope for
    result_type="worker_analysis"."""
    p = event["payload"]
    return _base_envelope(
        event,
        result_type="worker_analysis",
        agent_id=event.get("agent_id", "worker_safety_agent"),
        agent_version=event.get("agent_version", "0.0.0"),
        payload={
            "worker_id": p.get("worker_id"),
            "safety_status": p.get("safety_status"),
            "ppe_compliance": p.get("ppe_compliance"),
            "ppe_violations": p.get("ppe_violations", []),
            "zone_clearance": p.get("zone_clearance"),
            "proximity_alerts": p.get("proximity_alerts", []),
        },
    )


def zone_state_to_zone_analysis_raw(event: dict) -> dict:
    """ZoneStateV1 (real, verified) -> raw envelope for result_type=
    "zone_analysis" (AgentResultDTO.domain_name -> "zone"). See this
    module's docstring for exactly which fields are real vs. an honest
    documented absence (anomalies)."""
    p = event["payload"]
    risk_factors = tuple(p.get("active_sensor_alert_ids", []) or ()) + tuple(
        p.get("active_equipment_risk_ids", []) or ()
    )
    return _base_envelope(
        event,
        result_type="zone_analysis",
        agent_id="zone-intelligence-agent",
        agent_version=event.get("producer_version", "0.0.0"),
        payload={
            "zone_state": p.get("current_risk_level", "unknown"),
            "risk_factors": risk_factors,
            # Always empty -- see module docstring. Not a bug, not a
            # simplification: there is no real per-zone anomaly data on
            # the wire anywhere in this platform today.
            "anomalies": [],
            "worker_count": p.get("occupancy_count"),
            "equipment_ids": tuple(p.get("active_equipment_risk_ids", []) or ()),
        },
    )


class CachingEventPublisher:
    """EventPublisher (risk_orchestrator_agent.handlers.publishers'
    Protocol) that stores each SystemRiskAssessment in memory instead of
    logging it and discarding it -- the real gap #5 from
    docs/RECONCILIATION_REPORT.md (no outbound Kafka contract exists yet
    for RiskAssessmentV1) means there is nowhere else to durably land
    this today. Kept deliberately simple (dict keyed by zone_id, latest
    wins) to match this integration pass's other read-side caches
    (state_cache.py) rather than inventing new persistence."""

    def __init__(self, on_assessment=None) -> None:
        self._latest: dict[str, Any] = {}
        self._by_id: dict[str, Any] = {}
        # Optional sink invoked with each finalized assessment -- used to feed
        # the Response Agent (assessment -> ActionRequest) without the
        # orchestrator knowing anything about response logic.
        self._on_assessment = on_assessment

    async def publish(self, assessment) -> None:
        self._latest[assessment.zone_id] = assessment
        self._by_id[assessment.assessment_id] = assessment
        if self._on_assessment is not None:
            try:
                self._on_assessment(assessment)
            except Exception:  # noqa: BLE001 -- a response failure must not break risk publishing
                logger.exception("response_agent_failed", extra={"assessment_id": assessment.assessment_id})
        logger.info(
            "system_risk_assessment_cached",
            extra={
                "assessment_id": assessment.assessment_id,
                "zone_id": assessment.zone_id,
                "severity": assessment.severity.value,
                "global_score": assessment.global_score.value,
                "escalation_required": assessment.escalation_required,
            },
        )

    def clear(self) -> None:
        """Drops all cached assessments (demo reset only)."""
        self._latest.clear()
        self._by_id.clear()

    def latest_for_zone(self, zone_id: str):
        return self._latest.get(zone_id)

    def all_latest(self) -> list:
        return list(self._latest.values())

    def by_id(self, assessment_id: str):
        return self._by_id.get(assessment_id)
