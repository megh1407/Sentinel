"""
environmental_intelligence_agent.py

Environmental Intelligence Agent's BaseAgent implementation. Per
sentinel_agent_sdk/base_agent.py's docstring, process() is the only method
this repository's SDK calls -- consuming, publishing, retries, metrics,
tracing, health, and graceful shutdown are all AgentRunner's job, not
this file's.

WHY THIS FILE EXISTS: it replaces app/services/gas_agent.py's GasAgent
class, which was this repository's orchestrator, but was itself tightly
coupled to a REST request/response cycle (GasReadingRequest in,
GasAnalysisResponse out) that no longer exists. The preserved engine/*.py
services underneath GasAgent are UNCHANGED (see engine/'s files
directly); only the orchestration entrypoint is rewritten, because its old
shape (async def analyze(request) -> response) has no equivalent in
BaseAgent's process(event) -> event|list[event]|None contract.

Original 18-step pipeline (app/services/gas_agent.py: Step 1 through Step
18) is preserved below in the same order, as a documented, currently
UNREACHED code path -- see process()'s docstring for exactly why it isn't
invoked yet and what unblocks it.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from sentinel_agent_sdk import BaseAgent
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_contracts.agent_contracts.environment_analysis_v1 import (
    EnvironmentAnalysisV1,
    EnvironmentAnalysisPayload,
    HazardReading,
    HazardType,
    HazardTrend,
)
from sentinel_contracts.common.confidence_score import ConfidenceDerivation, ConfidenceScore
from sentinel_contracts.common.explanation_object import ExplanationObject
from sentinel_contracts.common.metadata import Environment, Metadata

from engine.enums import Severity
from sensor_snapshot_aggregator import SensorSnapshotAggregator

AGENT_NAME = "environmental_intelligence_agent"
AGENT_VERSION = "0.2.0"  # now publishes real EnvironmentAnalysisV1 (was a no-op stub)

# Closed vocabulary: which HazardType each recognized engine field maps to.
# A documented judgment call (like the Worker agent's), not invented data --
# these are the standard industrial-safety classifications for each species.
_FIELD_TO_HAZARD_TYPE: dict[str, HazardType] = {
    "methane": HazardType.flammable_gas,
    "voc": HazardType.flammable_gas,
    "carbon_monoxide": HazardType.toxic_gas,
    "hydrogen_sulfide": HazardType.toxic_gas,
    "ammonia": HazardType.toxic_gas,
    "oxygen": HazardType.oxygen_deficiency,
    "temperature": HazardType.high_temperature,
    "pressure": HazardType.high_pressure,
}
_FIELD_UNIT: dict[str, str] = {
    "methane": "ppm", "voc": "ppm", "carbon_monoxide": "ppm",
    "hydrogen_sulfide": "ppm", "ammonia": "ppm", "oxygen": "%",
    "temperature": "C", "pressure": "psi",
}
# Severity -> normalized risk contribution (documented mapping; the engine's
# RiskService uses a richer model, but for the per-hazard->analysis risk_score
# this monotonic ladder is explicit and auditable).
_SEVERITY_SCORE: dict[Severity, float] = {
    Severity.CRITICAL: 0.9,
    Severity.HIGH: 0.7,
    Severity.WARNING: 0.5,
    Severity.ADVISORY: 0.3,
}

from engine.history_manager import HistoryManager
from engine.validation_service import ValidationService
from engine.event_service import EventService
from engine.threshold_service import ThresholdService
from engine.trend_service import TrendService
from engine.prediction_service import PredictionService
from engine.correlation_service import CorrelationService
from engine.explosion_service import ExplosionService
from engine.gas_leak_service import GasLeakAnalysisService
from engine.hazard_classification_service import HazardClassificationService
from engine.historical_analytics_service import HistoricalAnalyticsService
from engine.risk_service import RiskService
from engine.recommendation_service import RecommendationService
from engine.explainability_service import ExplainabilityService
from engine.summary_service import SummaryService
from engine.evidence_service import EvidenceService
from engine.timeline_service import TimelineService
from engine.sensor_reliability_service import SensorReliabilityService
from engine.decision_service import DecisionService
from engine.audit_service import AuditService
from engine.diagnostics_service import DiagnosticsService


class EnvironmentalIntelligenceAgent(BaseAgent):
    def initialize(self) -> None:
        """Constructs every preserved engine service exactly as
        GasAgent.__init__ did (same classes, same constructor arguments --
        see migration report's constructor-signature cross-check). config
        (config.settings) is picked up implicitly by ThresholdService and
        PredictionService via their existing module-level `from config
        import settings` -- neither constructor takes it as an argument,
        because neither did before this migration."""
        self._aggregator = SensorSnapshotAggregator()
        self._history_manager = HistoryManager()
        # per-(zone,field) last measured value, for a real rising/falling/stable
        # trend on each HazardReading (not fabricated -- only set once a second
        # reading for that field actually arrives).
        self._last_values: dict[tuple[str, str], float] = {}

        self._validation_service = ValidationService()
        self._event_service = EventService()
        self._threshold_service = ThresholdService()
        self._trend_service = TrendService(self._history_manager)
        self._prediction_service = PredictionService()
        self._correlation_service = CorrelationService()
        self._explosion_service = ExplosionService()
        self._gas_leak_service = GasLeakAnalysisService(self._history_manager)
        self._hazard_classification_service = HazardClassificationService()
        self._historical_analytics_service = HistoricalAnalyticsService(self._history_manager)
        self._risk_service = RiskService()
        self._recommendation_service = RecommendationService()
        self._explainability_service = ExplainabilityService()
        self._summary_service = SummaryService()
        self._evidence_service = EvidenceService()
        self._timeline_service = TimelineService()
        self._sensor_reliability_service = SensorReliabilityService()
        self._decision_service = DecisionService()
        self._audit_service = AuditService()
        self._diagnostics_service = DiagnosticsService()

    def process(self, event: BaseModel) -> BaseModel | list[BaseModel] | None:
        """
        Current behavior: consumes SensorEvent, folds it into the
        per-zone snapshot via SensorSnapshotAggregator, and returns None.

        Why the 18-step engine pipeline below is not invoked from here yet
        -- both conditions must hold before it can be, and neither does:

          1. A complete snapshot (all 9 engine input fields) must be
             available for a zone. SensorSnapshotAggregator can only
             populate temperature/humidity/pressure from real traffic
             today -- methane/CO/H2S/O2/VOC/NH3 are unreachable until B3
             (gas-species identification on the wire) is resolved. See
             sensor_snapshot_aggregator.py's module docstring.

          2. Even given a complete snapshot, the pipeline's final output
             has no legal event to become. The original 18 steps produced
             a GasAnalysisResponse; this agent's registry entry
             (contracts/agent-registry/agents.yaml) requires producing
             `environment_analysis`, which has no generated,
             schema-registry-resolvable model yet (B1). Returning
             anything else here would mean fabricating a contract, which
             this migration does not do.

        Until both resolve, this method intentionally stops after
        aggregation and returns None -- AgentRunner commits the Kafka
        offset and moves on, with no event published and no side effect
        beyond the structured log line below. This is the honest
        behavior given B1/B3; it is not a placeholder pretending to work.

        engine/*.py's classes are fully constructed and ready to run the
        preserved pipeline (Step 1 validate -> Step 2 store history ->
        Step 3 threshold -> Step 4 trend -> Step 5 prediction -> Step 6
        correlation -> Step 7 explosion -> Step 8 gas leak -> Step 9
        hazard classification -> Step 10 historical analytics -> Step 11
        risk score -> Step 12 explainability -> Step 13 recommendations ->
        Step 14 events -> Step 15 summary -> Step 16 evidence -> Step 17
        timeline -> Step 18 sensor reliability, matching
        app/services/gas_agent.py's original step order exactly) the
        moment B1 and B3 resolve. Wiring that call back in at that point
        is a small, mechanical change to this method -- not a redesign of
        anything under engine/.
        """
        if not isinstance(event, SensorEventV1):
            self.logger.warning("environmental_intelligence_agent received unexpected event type",
                                 event_type=type(event).__name__)
            return None

        snapshot = self._aggregator.ingest(event)
        self.logger.info(
            "sensor snapshot updated",
            site_id=event.site_id,
            zone_id=event.zone_id,
            available_fields=sorted(snapshot.known_fields),
            dropped_gas_readings=snapshot.dropped_gas_readings,
        )
        if not snapshot.readings:
            # Only unrecognized/untagged readings so far -- nothing to analyze.
            return None

        return self._build_analysis(event, snapshot)

    def _build_analysis(self, event: SensorEventV1, snapshot) -> "EnvironmentAnalysisV1":
        """Runs the REAL, config-driven ThresholdService over the current
        per-zone snapshot and emits an EnvironmentAnalysisV1. The threshold
        values and severity ladder are the engine's own
        (engine/threshold_service.py + config.settings) -- this method adds no
        detection logic of its own, only the wire-format translation from the
        engine's violation dicts to the HazardReading contract the Risk
        Orchestrator consumes.
        """
        # ThresholdService is async; process() runs on the (sync) agent thread,
        # so drive it on a throwaway loop -- no loop is running here.
        violations = asyncio.run(self._threshold_service.check_all_thresholds(snapshot.readings))
        sev_by_field = {v["gas_type"]: v["severity"] for v in violations}
        thr_by_field = {v["gas_type"]: v["threshold_value"] for v in violations}

        hazards: list[HazardReading] = []
        worst_score = 0.0
        any_critical = False
        for field_name, value in sorted(snapshot.readings.items()):
            hazard_type = _FIELD_TO_HAZARD_TYPE.get(field_name)
            if hazard_type is None:
                continue
            severity = sev_by_field.get(field_name)
            breach = severity is not None
            score = _SEVERITY_SCORE.get(severity, 0.0) if breach else 0.0
            worst_score = max(worst_score, score)
            any_critical = any_critical or (severity == Severity.CRITICAL)

            key = (event.zone_id, field_name)
            prev = self._last_values.get(key)
            if prev is None or value == prev:
                trend = HazardTrend.stable
            elif value > prev:
                trend = HazardTrend.rising
            else:
                trend = HazardTrend.falling
            self._last_values[key] = value

            # Reference threshold: the breached level if any, else the
            # configured 'warning' threshold for that species.
            threshold_ppm = thr_by_field.get(field_name)
            if threshold_ppm is None:
                threshold_ppm = self._threshold_service.get_threshold(field_name, "warning")

            hazards.append(HazardReading(
                hazard_type=hazard_type,
                measured_value=value,
                unit=_FIELD_UNIT.get(field_name),
                threshold_ppm=threshold_ppm,
                threshold_breach=breach,
                trend=trend,
                sensor_ids=[snapshot.gas_sensor_ids.get(field_name, event.payload.sensor_id)],
            ))

        breached = [h for h in hazards if h.threshold_breach]
        confidence = 0.85
        now = datetime.now(timezone.utc)
        summary = (
            f"{len(breached)} hazard threshold breach(es) in zone {event.zone_id}: "
            + ", ".join(f"{h.hazard_type.value}={h.measured_value}{h.unit or ''}" for h in breached)
            if breached else
            f"No hazard thresholds breached in zone {event.zone_id} "
            f"({len(hazards)} reading(s) monitored)."
        )
        evidence = [
            f"{h.hazard_type.value} {h.measured_value}{h.unit or ''} "
            f"(threshold {h.threshold_ppm}, breach={h.threshold_breach}, trend={h.trend.value})"
            for h in hazards
        ]
        recommendations = (
            ["Initiate evacuation of affected zone."] if any_critical
            else ["Increase ventilation and monitor trend."] if breached
            else []
        )

        return EnvironmentAnalysisV1(
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
                summary=summary,
                confidence=ConfidenceScore(value=confidence, derivation=ConfidenceDerivation.RULE_BASED),
                evidence=[],
                reasoning_steps=[],
                generated_at=now,
            ),
            payload=EnvironmentAnalysisPayload(
                risk_score=worst_score,
                confidence=confidence,
                hazards=hazards,
                evacuation_required=any_critical,
                affected_zones=[event.zone_id],
                evidence=evidence,
                recommendations=recommendations,
                analyzed_at=now,
            ),
        )
