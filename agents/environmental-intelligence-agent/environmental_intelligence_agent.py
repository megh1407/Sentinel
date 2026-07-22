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

from pydantic import BaseModel

from sentinel_agent_sdk import BaseAgent
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1

from sensor_snapshot_aggregator import SensorSnapshotAggregator

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
        return None
