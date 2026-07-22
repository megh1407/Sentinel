"""domain/context/merge_rules.py — per-domain merge/conflict logic
(Phase 2.2 §5.3, §8).

Parses a raw `AgentResultDTO.payload` into the appropriate typed
sub-context Value Object, and implements the merge/conflict-resolution
rules from Phase 2.2 Section 8 (timestamp precedence, additive fields,
CONTESTED marking). Pure functions only — no I/O, no ports.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore
from risk_orchestrator_agent.domain.models.equipment_context import (
    EquipmentContext,
    FailurePrediction,
)
from risk_orchestrator_agent.domain.models.incident_context import (
    IncidentContext,
    KGPath,
    SimilarIncident,
)
from risk_orchestrator_agent.domain.models.maintenance_context import MaintenanceContext
from risk_orchestrator_agent.domain.models.permit_context import PermitContext, PermitConflict
from risk_orchestrator_agent.domain.models.sensor_context import Hazard, SensorContext
from risk_orchestrator_agent.domain.models.worker_context import ProximityAlert, WorkerContext
from risk_orchestrator_agent.domain.models.zone_context import Anomaly, ZoneContext
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.utils.time_utils import compute_age, utcnow

# Per-domain staleness thresholds (Phase 2.2 §3, configurable in a later
# phase via ConfigurationManager; sensible platform defaults for now).
STALENESS_THRESHOLDS: dict[str, timedelta] = {
    "worker": timedelta(seconds=2),
    "zone": timedelta(seconds=5),
    "sensor": timedelta(seconds=2),
    "equipment": timedelta(hours=1),
    "permit": timedelta(minutes=30),
    "incident": timedelta(hours=6),
    "maintenance": timedelta(hours=1),
}


def _age(analyzed_at, *, now=None) -> Age:
    return Age(duration=compute_age(analyzed_at, now=now))


def _is_stale(domain: str, analyzed_at, *, now=None) -> bool:
    threshold = STALENESS_THRESHOLDS.get(domain, timedelta(minutes=10))
    return _age(analyzed_at, now=now).exceeds(threshold)


def parse_worker(dto: AgentResultDTO) -> WorkerContext:
    p = dto.payload
    now = utcnow()
    return WorkerContext(
        worker_id=p["worker_id"],
        safety_status=p.get("safety_status", "unknown"),
        ppe_compliance=p.get("ppe_compliance"),
        ppe_violations=tuple(p.get("ppe_violations", ()) or ()),
        zone_clearance=p.get("zone_clearance"),
        proximity_alerts=tuple(
            ProximityAlert(a["hazard_type"], float(a["distance_m"]), float(a["safe_distance_m"]))
            for a in p.get("proximity_alerts", ()) or ()
        ),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("worker", dto.analyzed_at, now=now),
    )


def parse_zone(dto: AgentResultDTO) -> ZoneContext:
    p = dto.payload
    now = utcnow()
    return ZoneContext(
        zone_id=dto.zone_id,
        site_id=dto.site_id,
        zone_state=p.get("zone_state", "unknown"),
        risk_factors=tuple(p.get("risk_factors", ()) or ()),
        anomalies=tuple(
            Anomaly(a["anomaly_type"], a["description"], a["severity"], tuple(a.get("sensor_ids", ()) or ()))
            for a in p.get("anomalies", ()) or ()
        ),
        worker_count=p.get("worker_count"),
        equipment_ids=tuple(p.get("equipment_ids", ()) or ()),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("zone", dto.analyzed_at, now=now),
    )


def parse_equipment(dto: AgentResultDTO) -> EquipmentContext:
    p = dto.payload
    now = utcnow()
    fp = p.get("failure_prediction")
    return EquipmentContext(
        equipment_id=p["equipment_id"],
        health_index=p.get("health_index"),
        failure_prediction=(
            FailurePrediction(float(fp["probability"]), float(fp["predicted_window_h"]), fp["failure_mode"])
            if fp
            else None
        ),
        active_faults=tuple(p.get("active_faults", ()) or ()),
        overdue_tasks=tuple(p.get("overdue_tasks", ()) or ()),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("equipment", dto.analyzed_at, now=now),
    )


def parse_permit(dto: AgentResultDTO) -> PermitContext:
    p = dto.payload
    now = utcnow()
    return PermitContext(
        permit_id=p["permit_id"],
        permit_risk_level=p.get("permit_risk_level"),
        conflicts=tuple(
            PermitConflict(c["conflicting_permit_id"], c["conflict_type"], c["severity"])
            for c in p.get("conflicts", ()) or ()
        ),
        zone_compatibility=p.get("zone_compatibility"),
        zone_risk_at_issuance=p.get("zone_risk_at_issuance"),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("permit", dto.analyzed_at, now=now),
    )


def parse_sensor(dto: AgentResultDTO) -> SensorContext:
    p = dto.payload
    now = utcnow()
    return SensorContext(
        hazards=tuple(
            Hazard(
                h["hazard_type"],
                float(h["measured_value"]),
                h["unit"],
                h.get("threshold_ppm"),
                bool(h.get("threshold_breach", False)),
                h.get("trend", "stable"),
                tuple(h.get("sensor_ids", ()) or ()),
            )
            for h in p.get("hazards", ()) or ()
        ),
        evacuation_required=bool(p.get("evacuation_required", False)),
        affected_zones=tuple(p.get("affected_zones", ()) or ()),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("sensor", dto.analyzed_at, now=now),
    )


def parse_incident(dto: AgentResultDTO) -> IncidentContext:
    p = dto.payload
    now = utcnow()
    return IncidentContext(
        similar_incidents=tuple(
            SimilarIncident(
                i["incident_id"],
                float(i["similarity"]),
                i["incident_type"],
                i["severity"],
                i["site_id"],
                i["occurred_at"] if hasattr(i["occurred_at"], "tzinfo") else dto.analyzed_at,
                i.get("outcome", ""),
                i.get("root_cause", ""),
                i.get("vector_source", "incident_memory"),
            )
            for i in p.get("similar_incidents", ()) or ()
        ),
        historical_evidence=tuple(p.get("historical_evidence", ()) or ()),
        knowledge_graph_paths=tuple(
            KGPath(k["path"]) for k in p.get("knowledge_graph_paths", ()) or ()
        ),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("incident", dto.analyzed_at, now=now),
    )


def parse_maintenance(dto: AgentResultDTO) -> MaintenanceContext:
    p = dto.payload
    now = utcnow()
    return MaintenanceContext(
        equipment_id=p.get("equipment_id", ""),
        health_index=p.get("health_index"),
        overdue_tasks=tuple(p.get("overdue_tasks", ()) or ()),
        confidence=ConfidenceScore(dto.confidence),
        analyzed_at=dto.analyzed_at,
        age=_age(dto.analyzed_at, now=now),
        stale=_is_stale("maintenance", dto.analyzed_at, now=now),
    )


PARSERS = {
    "worker": parse_worker,
    "zone": parse_zone,
    "equipment": parse_equipment,
    "permit": parse_permit,
    "sensor": parse_sensor,
    "incident": parse_incident,
    "maintenance": parse_maintenance,
}


def merge_equipment_active_faults(
    existing: EquipmentContext | None, incoming: EquipmentContext
) -> EquipmentContext:
    """`active_faults` is deliberately additive across updates (Phase 2.2
    §4.2, §3) — never overwritten by a newer update that happens to omit
    a fault still in effect, until an explicit resolution is seen (i.e.
    a fault absent from `incoming.active_faults` is retained unless
    `incoming` is strictly newer AND the fault genuinely no longer
    appears — this simple model treats "not mentioned" as "still active"
    per the spec's stated rule)."""
    if existing is None:
        return incoming
    merged_faults = tuple(dict.fromkeys(existing.active_faults + incoming.active_faults))
    return replace(incoming, active_faults=merged_faults)


def resolve_by_timestamp(
    existing_analyzed_at, incoming_analyzed_at
) -> bool:
    """Timestamp precedence (Phase 2.2 §8.3): most recent `analyzed_at`
    wins. Returns True if `incoming` should replace `existing`."""
    return incoming_analyzed_at >= existing_analyzed_at
