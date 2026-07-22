"""
zone_intelligence_agent.py

Real business logic (not a stub). Maintains a live ZoneState projection per
zone in Redis, consuming SensorEvent, WorkerEvent, PermitEvent,
EquipmentRiskDetected, IncidentEvent, and MaintenanceRequired, and detects
eight kinds of anomaly:
  - OCCUPANCY_EXCEEDED: worker count in a zone exceeds a configured max.
  - ENVIRONMENTAL_HAZARD: a sensor threshold breach appears for the first
    time (not on every repeated reading of an already-known breach).
  - ZONE_HEALTH_DEGRADED: equipment risk OR high/critical-urgency pending
    maintenance becomes true TOGETHER WITH worker presence (spec's
    "equipment failure while workers are present" rule, extended to also
    cover MaintenanceRequired). Checked from BOTH directions -- a new
    risk/maintenance-need in an occupied zone, or a worker entering an
    already-risky zone -- firing only on the false->true transition.
  - PERMIT_CONFLICT: two currently-active permits in the same zone belong
    to a known-conflicting type pair (e.g. Hot Work + Confined Space).
    Same false->true transition guard as the other rules.
  - INCIDENT_FREQUENCY_EXCEEDED: more than INCIDENT_COUNT_THRESHOLD
    DISTINCT incidents reported in a zone within INCIDENT_WINDOW_SECONDS.
    Uses a Redis sorted set (IncidentTrackingRepository) keyed by
    incident_id, so a repeat report/update of the SAME incident doesn't
    inflate the count -- only genuinely new incidents do.
  - REPEATED_ANOMALIES: a META-rule, applied centrally in process() rather
    than inside any one handler. Counts anomaly OCCURRENCES (any type) per
    zone in a rolling window; if a zone keeps tripping different anomalies
    in quick succession, that pattern itself is flagged, on top of whatever
    each individual anomaly already meant. Excludes itself from its own
    count to avoid a feedback loop.
  - RAPID_STATE_CHANGE: another META-rule, applied centrally. Counts
    ZoneState UPDATES (regardless of whether they were anomalous) per zone
    in a rolling window -- a zone whose state keeps churning (flapping
    sensors, constant entry/exit, etc.) is itself worth flagging, even if
    no single update looked dangerous.
  - MISSING_SENSOR_DATA: BEST-EFFORT / PARTIAL implementation of Rule 6 --
    see the "known gap" note below before relying on this for anything.
    Tracks each sensor's last-seen timestamp; whenever ANY event touches a
    zone, checks whether other known sensors in that zone have gone quiet
    for longer than SENSOR_STALE_SECONDS. Fires once per sensor going
    stale (guarded by stale_sensor_ids), and un-flags a sensor if it
    reports again.

Every input event produces an updated ZoneState (published so downstream
consumers -- Risk Orchestrator, the dashboard -- always see current state),
and SOMETIMES additionally a ZoneAnomalyDetected event. This is why
process() returns a list, exercising sentinel_agent_sdk's multi-result
support.

PLATFORM LAYER (spec Parts 7, 11, 12, 13, 16), what's real vs what's not:
- Config (Part 13): config.py's ZoneConfig implements the full
  rule > site > agent > environment > global precedence. Real, unit-tested
  directly (test_zone_intelligence_agent_platform.py). Every threshold in
  this file is resolved through it at the point of use; GLOBAL_DEFAULTS
  preserves prior hardcoded values so nothing changes unless a more
  specific override is actually configured.
- Postgres (Part 7): ZoneRepository (libs/sentinel_state/postgres_repositories.py)
  persists zone_history/anomalies/audit_events. REAL, tested against a live
  local Postgres this session (same standard as HelloAgent's hello_pg) --
  see test_agent_writes_zone_history_and_anomaly_rows_to_real_postgres.
- Vector DB (Part 7): incident summaries stored via the ALREADY-BUILT,
  ALREADY-LIVE-TESTED IncidentEmbeddingRepository (Qdrant embedded mode).
  HONEST CAVEAT: the embedding itself (_pseudo_embedding) is a deterministic
  hash, NOT a real semantic model -- no embedding API is available in this
  environment. The storage/retrieval MECHANICS are real and tested; search
  RELEVANCE is not, until a real embedding call replaces the hash.
- Neo4j (Part 7): graph_projection_service.py wraps the ALREADY-BUILT
  ZoneGraphRepository/AssetGraphRepository, extended this session with
  worker/permit/incident relationship methods. NOT LIVE-TESTED -- Neo4j
  isn't installable in this sandbox (no apt package, no reachable download).
  Code-reviewed against the real neo4j driver's API only. No-op-safe: every
  rule above works with zero Neo4j dependency, exactly as before.
- Metrics (Part 11): zone_events_processed_total, zone_anomalies_detected_total,
  zone_state_updates_total, active_zone_count, active_incident_count are
  real self.metrics calls, tested via generate_latest(). zone_processing_
  duration_seconds is deliberately NOT re-implemented -- AgentRunner already
  emits an equivalent (agent_process_duration_seconds) for every agent;
  duplicating it here would double-count the same span under a new name.
- Health checks (Part 12): NOTHING agent-specific was built, because nothing
  needed to be -- StateContainer.health_checks() + HealthRegistry (both
  pre-existing, sentinel_agent_sdk/health.py) already auto-discover checks
  for whichever backends THIS agent's StateContainer actually constructs.
  Wiring postgres_session_factory/neo4j_driver/qdrant_client into main.py's
  StateContainer is what makes those checks appear; no new health.py needed.
- Observability (Part 16): correlation_id/causation_id and OpenTelemetry
  tracing spans are automatic, from AgentRunner -- NOT something this agent
  implements (an earlier pass in this project incorrectly claimed these were
  missing; they aren't, they're just handled one layer up, in runner.py).
  audit_id was a genuine gap -- not even HelloAgent sets it -- so this agent
  now populates it (Metadata.audit_id, deterministic per source event via
  uuid5) as a small platform-wide improvement, not just a local fix.
- Idempotency/retry/DLQ: inherited from sentinel_agent_sdk/sentinel_eventbus,
  same as every agent -- not reimplemented here.

FOLDER/CLASS STRUCTURE (spec Parts 17-18): deliberately NOT split into
router.py/analyzer.py/detector.py/explanation.py/models/ etc. The spec
document's diagram is generic and predates this actual codebase; the
REFERENCE agent that was actually built here (HelloAgent) is a single file,
with shared infrastructure living in libs/ (sentinel_state, sentinel_agent_sdk)
-- exactly the pattern this file follows. Forcing a bespoke 9-file split onto
just this one agent would make it inconsistent with every other agent and
with the platform's own reference implementation, for no functional benefit.
config.py and graph_projection_service.py are the two genuinely new files,
matching the SAME flat, one-file-per-concern convention libs/sentinel_state
already uses (redis_repositories.py, postgres_repositories.py, etc. sit
side by side, not nested in subpackages).

REMAINING GENUINE GAPS, not solved this session:
- MISSING_SENSOR_DATA (Rule 6) is still only a PARTIAL fix. It checks
  staleness opportunistically, when SOME OTHER event happens to touch the
  zone. A zone where EVERY sensor goes silent, and nothing else ever
  happens there again, will NEVER be checked -- there's no event left to
  trigger the check. A real fix needs a scheduler/heartbeat waking up on a
  timer independent of Kafka messages; sentinel_agent_sdk has none.
- EquipmentRiskDetected and MaintenanceRequired both have no "resolved"
  signal in their current contracts -- active_equipment_risk_ids and
  pending_critical_maintenance_asset_ids only grow. A real resolution path
  needs either a status field added to those events or separate *Resolved
  event types (MaintenanceEvent, a DIFFERENT existing contract with
  COMPLETED/OVERDUE status, would be the natural fit for the maintenance
  side -- not wired in yet).
- ZoneAnomalyType has no dedicated "equipment risk + occupancy" value, so
  that rule reuses ZONE_HEALTH_DEGRADED (closest existing fit).
- CONFLICTING_PERMIT_TYPE_PAIRS only encodes the spec's one worked example
  (Hot Work + Confined Space) -- config-resolvable now, but the actual pair
  set is still just that one guess, not a validated safety rule set.
- Rule 7's exact meaning ("rapid state changes") was ambiguous in the
  original spec; RAPID_STATE_CHANGE here means "N ZoneState updates in a
  rolling window," which is one reasonable reading, not the only one.

# PLATFORM_GAP (registry wiring, Phase 1.5/2): everything in this file is
# still fully active and unit-tested exactly as described above. What has
# changed is main.py, this agent's PRODUCTION Kafka wiring: consumption of
# EquipmentRiskDetected and MaintenanceRequired, and publishing of
# ZoneAnomalyDetected, are currently NOT subscribed/mapped there, because
# the frozen registry (kafka_topics.yaml) has no topic registered for any
# of the three yet -- see main.py's module docstring for the full
# explanation and exactly what's needed to re-enable each one. IncidentEvent
# consumption is also unwired there, for a related but distinct reason
# (its topic exists, but this agent isn't yet a documented consumer of it).
# None of that affects THIS file: process() below still dispatches all six
# event types and still returns ZoneAnomalyDetectedV1 results, and every
# test/acceptance-check/demo in this codebase that calls process() directly
# (bypassing main.py) continues to exercise the full behavior unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sentinel_agent_sdk import BaseAgent
from sentinel_contracts.common import ConfidenceScore, EvidenceItem, ExplanationObject
from sentinel_contracts.common.confidence_score import ConfidenceDerivation
from sentinel_contracts.common.metadata import Environment, Metadata
from sentinel_contracts.events.equipment_risk_detected_v1 import EquipmentRiskDetectedV1
from sentinel_contracts.events.incident_event_v1 import IncidentEventV1
from sentinel_contracts.events.maintenance_required_v1 import MaintenanceRequiredV1, MaintenanceUrgency
from sentinel_contracts.events.permit_event_v1 import PermitEventV1, PermitType
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_contracts.events.worker_event_v1 import WorkerEventV1
from sentinel_contracts.events.zone_anomaly_detected_v1 import (
    AnomalySeverity,
    ZoneAnomalyDetectedPayload,
    ZoneAnomalyDetectedV1,
    ZoneAnomalyType,
)
from sentinel_contracts.events.zone_state_v1 import RiskLevel, ZoneStatePayload, ZoneStateV1

from config import GLOBAL_DEFAULTS, ZoneConfig
from graph_projection_service import GraphProjectionService

# Module-level names kept for backward compatibility with existing tests and
# for at-a-glance readability -- these ARE exactly the GLOBAL (least specific)
# config layer now (see config.py). Actual runtime resolution goes through
# self.config.resolve(), which can be overridden per site/rule/environment;
# these constants are what resolve() falls back to when nothing more specific
# is configured, so nothing about existing behavior changes.
MAX_OCCUPANCY_PER_ZONE = GLOBAL_DEFAULTS["worker_threshold"]
INCIDENT_COUNT_THRESHOLD = GLOBAL_DEFAULTS["incident_count_threshold"]
INCIDENT_WINDOW_SECONDS = GLOBAL_DEFAULTS["incident_window_seconds"]
REPEATED_ANOMALY_THRESHOLD = GLOBAL_DEFAULTS["repeated_anomaly_threshold"]
REPEATED_ANOMALY_WINDOW_SECONDS = GLOBAL_DEFAULTS["repeated_anomaly_window_seconds"]
RAPID_STATE_CHANGE_THRESHOLD = GLOBAL_DEFAULTS["rapid_state_change_threshold"]
RAPID_STATE_CHANGE_WINDOW_SECONDS = GLOBAL_DEFAULTS["rapid_state_change_window_seconds"]
SENSOR_STALE_SECONDS = GLOBAL_DEFAULTS["sensor_stale_seconds"]
CONFLICTING_PERMIT_TYPE_PAIRS = GLOBAL_DEFAULTS["conflicting_permit_type_pairs"]

# Only HIGH/CRITICAL urgency maintenance needs correlate with worker presence for
# ZONE_HEALTH_DEGRADED -- LOW/MEDIUM is routine, not a live safety signal. Kept as
# a plain constant (not config-resolved): spec Part 13's config key list doesn't
# include this, and it's a business-rule classification, not a numeric threshold.
MAINTENANCE_URGENCY_CORRELATION_LEVELS = frozenset({MaintenanceUrgency.HIGH, MaintenanceUrgency.CRITICAL})


class ZoneIntelligenceAgent(BaseAgent):
    def initialize(self) -> None:
        super().initialize()
        self.config = ZoneConfig()
        # No-op-safe if Neo4j isn't configured for this deployment (see
        # graph_projection_service.py's docstring on live-test status).
        self.graph = GraphProjectionService(
            getattr(self.state, "zone_graph", None), getattr(self.state, "asset_graph", None)
        )
        # Spec Part 11's metrics, the ones NOT already covered generically by
        # AgentRunner (which already emits agent_process_total and
        # agent_process_duration_seconds for every agent -- duplicating that
        # here as "zone_processing_duration_seconds" would just double-count
        # the same span, so it's deliberately not re-implemented).
        self._events_processed = self.metrics.counter(
            "zone_events_processed_total", "Count of input events processed, by type", labels=["event_type"])
        self._anomalies_detected_metric = self.metrics.counter(
            "zone_anomalies_detected_total", "Count of anomalies detected, by type", labels=["anomaly_type"])
        self._state_updates = self.metrics.counter(
            "zone_state_updates_total", "Count of ZoneState publishes")
        self._active_zone_count = self.metrics.gauge(
            "active_zone_count", "Number of distinct zones with known state in Redis")
        self._active_incident_count = self.metrics.gauge(
            "active_incident_count", "Current recent_incident_count per zone (sum across zones via PromQL)",
            labels=["zone_id"])

    def process(
        self, event: SensorEventV1 | WorkerEventV1 | PermitEventV1 | EquipmentRiskDetectedV1
                     | IncidentEventV1 | MaintenanceRequiredV1
    ) -> list | None:
        if isinstance(event, SensorEventV1):
            results = self._handle_sensor_event(event)
        elif isinstance(event, WorkerEventV1):
            results = self._handle_worker_event(event)
        elif isinstance(event, PermitEventV1):
            results = self._handle_permit_event(event)
        elif isinstance(event, EquipmentRiskDetectedV1):
            # PLATFORM_GAP: unreachable in production (main.py doesn't
            # subscribe to this topic yet -- no registry entry exists).
            # Still fully exercised by acceptance_check.py/demo.py/tests,
            # which call process() directly. See module docstring.
            results = self._handle_equipment_risk_event(event)
        elif isinstance(event, IncidentEventV1):
            # PLATFORM_GAP: unreachable in production (main.py doesn't
            # subscribe -- this agent isn't yet a documented registry
            # consumer of sentinel.incident.events.v1). See module docstring.
            results = self._handle_incident_event(event)
        elif isinstance(event, MaintenanceRequiredV1):
            # PLATFORM_GAP: unreachable in production (main.py doesn't
            # subscribe -- no registry entry exists). See module docstring.
            results = self._handle_maintenance_required_event(event)
        else:
            self.logger.warning("received an event type this agent doesn't handle", event_type=type(event).__name__)
            return None

        self._events_processed.labels(event_type=type(event).__name__).inc()
        if self.state.zone_pg is not None:
            self.state.zone_pg.record_audit_event(
                source_event_id=str(event.event_id), source_event_type=type(event).__name__,
                zone_id=getattr(event, "zone_id", None), correlation_id=str(event.correlation_id),
                causation_id=str(getattr(event, "causation_id", "")) or None,
            )

        # Rules 7 and 8 are META-rules that look across whatever the specific
        # handler above just produced, so they're applied once, centrally,
        # rather than duplicated inside every _handle_* method.
        # Order matters here: rapid_state_change and missing_sensor_data can each
        # ADD an anomaly to results. repeated_anomaly counts "how many anomalies
        # just fired" -- it must run LAST, or it silently misses anomalies the
        # other two just added (a real bug, found via
        # test_zone_agent_job_verification.py's Rule 8 test, fixed here).
        results = self._apply_rapid_state_change_rule(event, results)
        results = self._apply_missing_sensor_data_rule(event, results)
        results = self._apply_repeated_anomaly_rule(event, results)
        return results

    # -- state helpers --

    def _load_or_init_zone_state(self, zone_id: str, site_id: str) -> ZoneStateV1:
        existing = self.state.zone.get(zone_id, ZoneStateV1)
        if existing is not None:
            return existing
        if self.state.redis_client is not None:
            # Best-effort active_zone_count tracking -- a plain Redis SET of
            # zone_ids we've ever seen. Not TTL'd (deliberately -- a zone doesn't
            # stop existing just because Redis's zone-state TTL expired).
            self.state.redis_client.sadd("zone_intelligence:known_zone_ids", zone_id)
            self._active_zone_count.set(self.state.redis_client.scard("zone_intelligence:known_zone_ids"))
        return ZoneStateV1(
            event_id=uuid.uuid4(),
            event_timestamp=datetime.now(timezone.utc),
            correlation_id=uuid.uuid4(),
            producer_service="zone-intelligence-agent",
            producer_version="0.1.0",
            site_id=site_id,
            zone_id=zone_id,
            partition_key=zone_id,
            metadata=Metadata(schema_id=0, schema_version=1, environment=Environment.DEV),
            payload=ZoneStatePayload(
                current_risk_level=RiskLevel.LOW,
                active_permit_ids=[],
                active_permit_types={},
                occupancy_count=0,
                active_sensor_alert_ids=[],
                active_equipment_risk_ids=[],
                recent_incident_count=0,
                pending_critical_maintenance_asset_ids=[],
                last_sensor_reading_ts={},
                stale_sensor_ids=[],
                last_updated=datetime.now(timezone.utc),
                is_stale=False,
            ),
        )

    # Fixed namespace so the SAME source event always derives the SAME audit_id,
    # whether it's used on the ZoneState publish or an anomaly derived from that
    # same event -- deterministic, no extra state threading required. audit_id
    # is a genuine platform-wide gap (not even HelloAgent sets it -- checked);
    # this agent leads by populating it rather than leaving it None like everyone else.
    _AUDIT_ID_NAMESPACE = uuid.UUID("6c9b1f2e-6b4b-4e9c-9c1b-2f6a1e8d5c3a")

    def _derive_audit_id(self, source_event) -> str:
        return str(uuid.uuid5(self._AUDIT_ID_NAMESPACE, str(source_event.event_id)))

    def _save_and_republish(self, zone_state: ZoneStateV1, source_event) -> ZoneStateV1:
        zone_state.event_id = uuid.uuid4()
        zone_state.event_timestamp = datetime.now(timezone.utc)
        zone_state.correlation_id = source_event.correlation_id
        zone_state.causation_id = source_event.event_id
        zone_state.metadata.audit_id = self._derive_audit_id(source_event)
        zone_state.payload.last_updated = datetime.now(timezone.utc)
        self.state.zone.set(zone_state.zone_id, zone_state, ttl_seconds=self.config.resolve(
            "cache_ttl_seconds", site_id=zone_state.site_id))
        self._state_updates.inc()
        if self.state.zone_pg is not None:
            self.state.zone_pg.record_zone_state(
                zone_state_event_id=str(zone_state.event_id), zone_id=zone_state.zone_id,
                site_id=zone_state.site_id, occupancy_count=zone_state.payload.occupancy_count,
                current_risk_level=zone_state.payload.current_risk_level.value,
            )
        return zone_state

    def _build_anomaly(self, zone_state: ZoneStateV1, source_event, anomaly_type: ZoneAnomalyType,
                        severity: AnomalySeverity, summary: str, evidence_description: str,
                        rule_id: str, confidence: float) -> ZoneAnomalyDetectedV1:
        anomaly_id = str(uuid.uuid4())
        anomaly = ZoneAnomalyDetectedV1(
            event_id=uuid.uuid4(),
            event_timestamp=datetime.now(timezone.utc),
            correlation_id=source_event.correlation_id,
            causation_id=source_event.event_id,
            producer_version="0.1.0",
            site_id=zone_state.site_id,
            zone_id=zone_state.zone_id,
            partition_key=zone_state.zone_id,
            metadata=Metadata(schema_id=0, schema_version=1, environment=Environment.DEV,
                               audit_id=self._derive_audit_id(source_event)),
            explanation=ExplanationObject(
                summary=summary,
                confidence=ConfidenceScore(value=confidence, derivation=ConfidenceDerivation.RULE_BASED,
                                            rule_id=rule_id, rule_version=1),
                evidence=[EvidenceItem(
                    source_event_id=str(source_event.event_id),
                    source_type=type(source_event).__name__.replace("V1", ""),
                    description=evidence_description,
                    weight=1.0,
                    timestamp=source_event.event_timestamp,
                )],
                reasoning_steps=[f"Rule '{rule_id}' fired", summary],
                risk_contributors=[],
                rule_metadata={"rule_id": rule_id, "rule_version": "1"},
                generated_at=datetime.now(timezone.utc),
            ),
            payload=ZoneAnomalyDetectedPayload(
                anomaly_id=anomaly_id,
                anomaly_type=anomaly_type,
                severity=severity,
            ),
        )
        self._anomalies_detected_metric.labels(anomaly_type=anomaly_type.value).inc()
        if self.state.zone_pg is not None:
            self.state.zone_pg.record_anomaly(
                anomaly_event_id=str(anomaly.event_id), zone_id=zone_state.zone_id,
                anomaly_type=anomaly_type.value, severity=severity.value, rule_id=rule_id,
                confidence=confidence, summary=summary,
            )
        return anomaly

    # -- event handlers --

    def _apply_repeated_anomaly_rule(self, source_event, results: list) -> list:
        new_anomalies = [
            r for r in results
            if isinstance(r, ZoneAnomalyDetectedV1) and r.payload.anomaly_type != ZoneAnomalyType.REPEATED_ANOMALIES
        ]
        if not new_anomalies:
            return results  # nothing to count -- this event didn't trigger any anomaly

        zone_id = new_anomalies[0].zone_id
        now_ts = source_event.event_timestamp.timestamp()
        window = self.config.resolve("repeated_anomaly_window_seconds", site_id=source_event.site_id,
                                      rule_id="repeated_anomalies")
        threshold = self.config.resolve("repeated_anomaly_threshold", site_id=source_event.site_id,
                                         rule_id="repeated_anomalies")

        before_count = self.state.anomalies.count_recent(zone_id, window, now_ts)
        for anomaly in new_anomalies:
            # Recorded by the anomaly's OWN event_id, not the source event's, since a single
            # source event can (rarely) produce more than one anomaly and each should count once.
            self.state.anomalies.record_anomaly(zone_id, str(anomaly.event_id), now_ts)
        after_count = self.state.anomalies.count_recent(zone_id, window, now_ts)

        was_exceeded = before_count > threshold
        now_exceeded = after_count > threshold
        if now_exceeded and not was_exceeded:
            zone_state = next(r for r in results if isinstance(r, ZoneStateV1))
            triggering_types = ", ".join(a.payload.anomaly_type.value for a in new_anomalies)
            meta_anomaly = self._build_anomaly(
                zone_state, source_event,
                anomaly_type=ZoneAnomalyType.REPEATED_ANOMALIES,
                severity=AnomalySeverity.HIGH,
                summary=f"Zone {zone_id} has triggered {after_count} anomalies in the last "
                        f"{window // 60} minutes (max is "
                        f"{threshold}) -- this zone may need direct attention "
                        f"rather than per-anomaly handling.",
                evidence_description=f"New anomaly type(s) [{triggering_types}] pushed the "
                                      f"{window // 60}m anomaly count to {after_count}.",
                rule_id="repeated_anomalies",
                confidence=0.85,
            )
            results = results + [meta_anomaly]
            self.logger.warning("zone anomaly detected", zone_id=zone_id, anomaly_type="REPEATED_ANOMALIES")

        return results

    def _apply_rapid_state_change_rule(self, source_event, results: list) -> list:
        if not results or not isinstance(results[0], ZoneStateV1):
            return results  # e.g. EquipmentRiskDetected/MaintenanceRequired with no zone_id -> []

        zone_state = results[0]
        zone_id = zone_state.zone_id
        now_ts = source_event.event_timestamp.timestamp()
        window = self.config.resolve("rapid_state_change_window_seconds", site_id=source_event.site_id,
                                      rule_id="rapid_state_change")
        threshold = self.config.resolve("rapid_state_change_threshold", site_id=source_event.site_id,
                                         rule_id="rapid_state_change")

        before_count = self.state.state_changes.count_recent(zone_id, window, now_ts)
        self.state.state_changes.record_state_change(zone_id, str(zone_state.event_id), now_ts)
        after_count = self.state.state_changes.count_recent(zone_id, window, now_ts)

        was_exceeded = before_count > threshold
        now_exceeded = after_count > threshold
        if now_exceeded and not was_exceeded:
            anomaly = self._build_anomaly(
                zone_state, source_event,
                anomaly_type=ZoneAnomalyType.RAPID_STATE_CHANGE,
                severity=AnomalySeverity.MEDIUM,
                summary=f"Zone {zone_id} has updated its state {after_count} times in the last "
                        f"{window // 60} minutes, exceeding the configured "
                        f"maximum of {threshold} -- the zone may be unstable.",
                evidence_description=f"This is state update #{after_count} for zone {zone_id} within the "
                                      f"{window // 60}m window.",
                rule_id="rapid_state_change",
                confidence=0.7,
            )
            results = results + [anomaly]
            self.logger.warning("zone anomaly detected", zone_id=zone_id, anomaly_type="RAPID_STATE_CHANGE")

        return results

    def _apply_missing_sensor_data_rule(self, source_event, results: list) -> list:
        # PARTIAL Rule 6 -- see module docstring's MISSING_SENSOR_DATA known gap.
        # Only runs opportunistically, when some OTHER event already touched this zone.
        if not results or not isinstance(results[0], ZoneStateV1):
            return results

        zone_state = results[0]
        if not zone_state.payload.last_sensor_reading_ts:
            return results

        stale_seconds = self.config.resolve("sensor_stale_seconds", site_id=source_event.site_id,
                                             rule_id="missing_sensor_data")
        now_ts = source_event.event_timestamp.timestamp()
        newly_stale = [
            sensor_id for sensor_id, last_ts in zone_state.payload.last_sensor_reading_ts.items()
            if (now_ts - last_ts) > stale_seconds and sensor_id not in zone_state.payload.stale_sensor_ids
        ]
        if not newly_stale:
            return results

        zone_state.payload.stale_sensor_ids.extend(newly_stale)
        cache_ttl = self.config.resolve("cache_ttl_seconds", site_id=source_event.site_id)
        self.state.zone.set(zone_state.zone_id, zone_state, ttl_seconds=cache_ttl)  # persist updated stale flags

        anomaly = self._build_anomaly(
            zone_state, source_event,
            anomaly_type=ZoneAnomalyType.MISSING_SENSOR_DATA,
            severity=AnomalySeverity.HIGH,
            summary=f"Sensor(s) {', '.join(newly_stale)} in zone {zone_state.zone_id} haven't reported "
                    f"in over {stale_seconds // 60} minutes. NOTE: partial detection -- only "
                    f"checked because another event happened to touch this zone; see agent known-gaps.",
            evidence_description=f"No reading from sensor(s) {', '.join(newly_stale)} for over "
                                  f"{stale_seconds // 60}m, checked as of this "
                                  f"{type(source_event).__name__.replace('V1', '')} event.",
            rule_id="missing_sensor_data",
            confidence=0.6,
        )
        results = results + [anomaly]
        self.logger.warning("zone anomaly detected", zone_id=zone_state.zone_id, anomaly_type="MISSING_SENSOR_DATA")
        return results

    def _handle_sensor_event(self, event: SensorEventV1) -> list:
        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        sensor_id = event.payload.sensor_id
        was_already_alerting = sensor_id in zone_state.payload.active_sensor_alert_ids

        results = []
        if event.payload.threshold_breached:
            if sensor_id not in zone_state.payload.active_sensor_alert_ids:
                zone_state.payload.active_sensor_alert_ids.append(sensor_id)
        else:
            if sensor_id in zone_state.payload.active_sensor_alert_ids:
                zone_state.payload.active_sensor_alert_ids.remove(sensor_id)

        # Feeds the (partial, see docstring) missing-sensor-data rule -- every
        # reading, breached or not, counts as "this sensor is alive."
        zone_state.payload.last_sensor_reading_ts[sensor_id] = event.event_timestamp.timestamp()
        if sensor_id in zone_state.payload.stale_sensor_ids:
            zone_state.payload.stale_sensor_ids.remove(sensor_id)

        zone_state.payload.current_risk_level = (
            RiskLevel.HIGH if zone_state.payload.active_sensor_alert_ids else RiskLevel.LOW
        )

        zone_state = self._save_and_republish(zone_state, event)
        results.append(zone_state)

        # Only fire a NEW anomaly the first time this sensor's breach is seen
        # -- not on every repeated reading of an already-known breach, to
        # avoid flooding downstream with duplicate anomaly events.
        if event.payload.threshold_breached and not was_already_alerting:
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.ENVIRONMENTAL_HAZARD,
                severity=AnomalySeverity.HIGH,
                summary=f"Sensor {sensor_id} in zone {event.zone_id} breached its threshold "
                        f"({event.payload.value} {event.payload.unit}).",
                evidence_description=f"{event.payload.sensor_type.value} reading of {event.payload.value} "
                                      f"{event.payload.unit} exceeded the configured threshold.",
                rule_id="sensor_threshold_breach",
                confidence=0.95,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="ENVIRONMENTAL_HAZARD")

        return results

    def _handle_worker_event(self, event: WorkerEventV1) -> list:
        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        worker_id = event.payload.worker_id
        has_health_risk = self._has_equipment_health_risk(zone_state.payload)
        was_condition_active = has_health_risk and zone_state.payload.occupancy_count > 0

        if event.payload.event_kind.value == "ZONE_ENTRY":
            self.state.worker.add_presence(event.zone_id, worker_id)
            self.graph.project_worker_entry(event.zone_id, worker_id)
        elif event.payload.event_kind.value == "ZONE_EXIT":
            self.state.worker.remove_presence(event.zone_id, worker_id)
            self.graph.project_worker_exit(event.zone_id, worker_id)

        occupancy = len(self.state.worker.get_zone_occupancy(event.zone_id))
        zone_state.payload.occupancy_count = occupancy

        zone_state = self._save_and_republish(zone_state, event)
        results = [zone_state]

        worker_threshold = self.config.resolve("worker_threshold", site_id=event.site_id,
                                                 rule_id="occupancy_limit")
        if occupancy > worker_threshold:
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.OCCUPANCY_EXCEEDED,
                severity=AnomalySeverity.HIGH,
                summary=f"Zone {event.zone_id} occupancy of {occupancy} exceeds the configured maximum "
                        f"of {worker_threshold}.",
                evidence_description=f"Worker {worker_id} entered zone {event.zone_id}, "
                                      f"bringing occupancy to {occupancy}.",
                rule_id="occupancy_limit",
                confidence=0.99,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="OCCUPANCY_EXCEEDED")

        # Correlation check, direction 2 of 2: a worker just walked into a
        # zone that ALREADY has an active equipment risk or urgent maintenance
        # need. This is the false->true transition even though no new
        # equipment/maintenance event fired.
        now_condition_active = has_health_risk and occupancy > 0
        if now_condition_active and not was_condition_active:
            causes = zone_state.payload.active_equipment_risk_ids + zone_state.payload.pending_critical_maintenance_asset_ids
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.ZONE_HEALTH_DEGRADED,
                severity=AnomalySeverity.CRITICAL,
                summary=f"Zone {event.zone_id} has an active equipment/maintenance health risk on "
                        f"asset(s) {', '.join(causes)} while {occupancy} worker(s) are now present.",
                evidence_description=f"Worker {worker_id} entered zone {event.zone_id}, which already had "
                                      f"an active equipment risk or urgent pending maintenance on asset(s) "
                                      f"{', '.join(causes)}.",
                rule_id="equipment_risk_with_workers_present",
                confidence=0.9,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="ZONE_HEALTH_DEGRADED")

        return results

    def _handle_maintenance_required_event(self, event: MaintenanceRequiredV1) -> list:
        if event.zone_id is None:
            # Same contract-level gap as EquipmentRiskDetected: zone_id is optional
            # because the producing agent doesn't always know the zone. Without it
            # we can't correlate, so we drop it rather than guessing.
            self.logger.warning("maintenance required event has no zone_id, cannot correlate",
                                 asset_id=event.payload.asset_id)
            return []

        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        asset_id = event.payload.asset_id
        is_urgent = event.payload.urgency in MAINTENANCE_URGENCY_CORRELATION_LEVELS

        was_condition_active = (
            self._has_equipment_health_risk(zone_state.payload) and zone_state.payload.occupancy_count > 0
        )

        if is_urgent:
            if asset_id not in zone_state.payload.pending_critical_maintenance_asset_ids:
                zone_state.payload.pending_critical_maintenance_asset_ids.append(asset_id)
        # LOW/MEDIUM urgency is routine -- recorded nowhere for now (no field for it),
        # since it isn't a live safety signal. See module docstring's known gaps.

        zone_state = self._save_and_republish(zone_state, event)
        results = [zone_state]

        now_condition_active = (
            self._has_equipment_health_risk(zone_state.payload) and zone_state.payload.occupancy_count > 0
        )
        if now_condition_active and not was_condition_active:
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.ZONE_HEALTH_DEGRADED,
                severity=AnomalySeverity.CRITICAL,
                summary=f"Asset {asset_id} in zone {event.zone_id} has {event.payload.urgency.value}-urgency "
                        f"maintenance pending ({event.payload.recommended_action}) while "
                        f"{zone_state.payload.occupancy_count} worker(s) are present.",
                evidence_description=f"MaintenanceRequired for asset {asset_id} at "
                                      f"{event.payload.urgency.value} urgency, in a zone with workers "
                                      f"currently present.",
                rule_id="equipment_risk_with_workers_present",
                confidence=0.85,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="ZONE_HEALTH_DEGRADED")

        return results

    def _has_conflicting_permits(self, active_permit_types: dict[str, str], site_id: str) -> bool:
        active_types = set(active_permit_types.values())
        pairs = self.config.resolve("conflicting_permit_type_pairs", site_id=site_id, rule_id="conflicting_permits")
        return any(pair <= active_types for pair in pairs)

    def _handle_permit_event(self, event: PermitEventV1) -> list:
        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        permit_id = event.payload.permit_id
        permit_type = event.payload.permit_type.value
        status = event.payload.status.value

        was_conflict_active = self._has_conflicting_permits(zone_state.payload.active_permit_types, event.site_id)

        if status == "ACTIVE":
            if permit_id not in zone_state.payload.active_permit_ids:
                zone_state.payload.active_permit_ids.append(permit_id)
            zone_state.payload.active_permit_types[permit_id] = permit_type
        elif status in ("CLOSED", "EXPIRED", "SUSPENDED"):
            if permit_id in zone_state.payload.active_permit_ids:
                zone_state.payload.active_permit_ids.remove(permit_id)
            zone_state.payload.active_permit_types.pop(permit_id, None)
        self.graph.project_permit(event.zone_id, permit_id, permit_type, status)

        zone_state = self._save_and_republish(zone_state, event)
        results = [zone_state]

        # Fires only on the false->true transition -- e.g. a Hot Work permit going ACTIVE
        # while a Confined Space permit is already active in the same zone (or vice versa).
        # A third, unrelated permit changing status afterward won't refire this.
        now_conflict_active = self._has_conflicting_permits(zone_state.payload.active_permit_types, event.site_id)
        if now_conflict_active and not was_conflict_active:
            active_types = sorted(set(zone_state.payload.active_permit_types.values()))
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.PERMIT_CONFLICT,
                severity=AnomalySeverity.HIGH,
                summary=f"Zone {event.zone_id} has conflicting active permit types: "
                        f"{', '.join(active_types)}.",
                evidence_description=f"Permit {permit_id} ({permit_type}) became {status}, creating a "
                                      f"known-conflicting combination with other active permits in the zone.",
                rule_id="conflicting_permits",
                confidence=0.95,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="PERMIT_CONFLICT")

        return results

    def _has_equipment_health_risk(self, payload: ZoneStatePayload) -> bool:
        return bool(payload.active_equipment_risk_ids) or bool(payload.pending_critical_maintenance_asset_ids)

    def _handle_equipment_risk_event(self, event: EquipmentRiskDetectedV1) -> list:
        if event.zone_id is None:
            # EquipmentRiskDetected's zone_id is optional at the contract level (equipment
            # isn't always mapped to a zone yet); without it we can't correlate, so we drop it
            # rather than guessing. A real fix is the Equipment agent always resolving zone_id
            # via Neo4j Equipment->Zone before publishing -- out of scope for this step.
            self.logger.warning("equipment risk event has no zone_id, cannot correlate",
                                 asset_id=event.payload.asset_id)
            return []

        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        asset_id = event.payload.asset_id

        # Correlation check, direction 1 of 2: an equipment risk just arrived in a
        # zone that ALREADY has workers present.
        was_condition_active = (
            self._has_equipment_health_risk(zone_state.payload) and zone_state.payload.occupancy_count > 0
        )

        if asset_id not in zone_state.payload.active_equipment_risk_ids:
            zone_state.payload.active_equipment_risk_ids.append(asset_id)
        self.graph.project_equipment(event.zone_id, asset_id, criticality="HIGH")

        zone_state = self._save_and_republish(zone_state, event)
        results = [zone_state]

        now_condition_active = (
            self._has_equipment_health_risk(zone_state.payload) and zone_state.payload.occupancy_count > 0
        )
        if now_condition_active and not was_condition_active:
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.ZONE_HEALTH_DEGRADED,
                severity=AnomalySeverity.CRITICAL,
                summary=f"Equipment {asset_id} in zone {event.zone_id} shows "
                        f"{event.payload.risk_type.value} while "
                        f"{zone_state.payload.occupancy_count} worker(s) are present.",
                evidence_description=f"Equipment risk '{event.payload.risk_type.value}' detected for asset "
                                      f"{asset_id} in a zone with workers currently present.",
                rule_id="equipment_risk_with_workers_present",
                confidence=0.9,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id, anomaly_type="ZONE_HEALTH_DEGRADED")

        return results

    def _handle_incident_event(self, event: IncidentEventV1) -> list:
        zone_state = self._load_or_init_zone_state(event.zone_id, event.site_id)
        now_ts = event.event_timestamp.timestamp()
        window = self.config.resolve("incident_window_seconds", site_id=event.site_id,
                                      rule_id="incident_frequency")
        threshold = self.config.resolve("incident_count_threshold", site_id=event.site_id,
                                         rule_id="incident_frequency")

        # Recording is keyed by incident_id, so a repeat report/update of the SAME
        # incident (see IncidentEvent's docstring: report/update/close all share one
        # event type) doesn't inflate the count -- only genuinely distinct incidents do.
        before_count = self.state.incidents.count_recent(event.zone_id, window, now_ts)
        self.state.incidents.record_incident(event.zone_id, event.payload.incident_id, now_ts)
        after_count = self.state.incidents.count_recent(event.zone_id, window, now_ts)

        self.graph.project_incident(event.zone_id, event.payload.incident_id,
                                     event.payload.incident_type, event.payload.severity.value)
        self._store_incident_embedding(event)

        zone_state.payload.recent_incident_count = after_count
        zone_state = self._save_and_republish(zone_state, event)
        results = [zone_state]
        self._active_incident_count.labels(zone_id=event.zone_id).set(after_count)

        was_exceeded = before_count > threshold
        now_exceeded = after_count > threshold
        if now_exceeded and not was_exceeded:
            anomaly = self._build_anomaly(
                zone_state, event,
                anomaly_type=ZoneAnomalyType.INCIDENT_FREQUENCY_EXCEEDED,
                severity=AnomalySeverity.CRITICAL,
                summary=f"Zone {event.zone_id} has had {after_count} distinct incidents in the last "
                        f"{window // 3600}h, exceeding the configured maximum of "
                        f"{threshold}.",
                evidence_description=f"Incident {event.payload.incident_id} "
                                      f"({event.payload.severity.value}) reported in zone {event.zone_id}, "
                                      f"bringing the {window // 3600}h count to {after_count}.",
                rule_id="incident_frequency",
                confidence=0.9,
            )
            results.append(anomaly)
            self.logger.warning("zone anomaly detected", zone_id=event.zone_id,
                                 anomaly_type="INCIDENT_FREQUENCY_EXCEEDED")

        return results

    def _store_incident_embedding(self, event: IncidentEventV1) -> None:
        """Vector DB usage (spec Part 7: 'zone incident summaries'). Uses the
        ALREADY-BUILT, ALREADY-LIVE-TESTED IncidentEmbeddingRepository
        (Qdrant embedded mode). No-ops if Qdrant isn't configured.

        HONEST CAVEAT: _pseudo_embedding below is NOT a real semantic
        embedding model -- there's no embedding API available in this
        environment/session. It's a small deterministic hash-based vector,
        good enough to prove the storage/retrieval MECHANICS work (upsert,
        filtered similarity search), but two incidents with similar
        meaning but different wording will NOT necessarily land near each
        other in vector space the way a real embedding model would. Swap
        in a real embedding call here before relying on search relevance.
        """
        if self.state.incident_embeddings is None:
            return
        text = f"{event.payload.incident_type} {event.payload.severity.value}"
        vector = self._pseudo_embedding(text, dims=self.state.incident_embeddings.vector_size)
        # Qdrant point IDs must be a UUID or unsigned int -- NOT an arbitrary string
        # (verified against the real embedded client; "INC-1" is rejected outright).
        # uuid5 gives a deterministic point id from the incident_id, so re-processing
        # the same incident (report/update/close, per IncidentEvent's own docstring)
        # upserts the SAME point rather than creating duplicates.
        point_id = str(uuid.uuid5(self._AUDIT_ID_NAMESPACE, f"incident:{event.payload.incident_id}"))
        self.state.incident_embeddings.upsert(
            id=point_id,
            vector=vector,
            metadata={"incident_id": event.payload.incident_id, "site_id": event.site_id,
                      "zone_id": event.zone_id, "incident_type": event.payload.incident_type,
                      "severity": event.payload.severity.value},
        )

    @staticmethod
    def _pseudo_embedding(text: str, dims: int) -> list[float]:
        import hashlib
        digest = hashlib.sha256(text.encode()).digest()
        return [(digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(dims)]