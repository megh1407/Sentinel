"""memory/adapters/_risk_context_codec.py — RiskContext <-> JSON-safe dict
codec, used by `redis_context_adapter.py`.

Not a domain module: this is adapter-internal serialization logic (FRS
§6's "Repository DTOs... never exposed outside memory/" — the physical
row/document shape an adapter maps to/from is adapter-internal, not a
separately-named DTO file).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

from risk_orchestrator_agent.domain.models.correlation_finding import (
    CorrelationFinding,
    CorrelationType,
)
from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore
from risk_orchestrator_agent.domain.models.equipment_context import (
    EquipmentContext,
    FailurePrediction,
)
from risk_orchestrator_agent.domain.models.evidence import EvidenceItem, EvidenceType
from risk_orchestrator_agent.domain.models.evidence_collection import EvidenceCollection
from risk_orchestrator_agent.domain.models.historical_context import (
    HistoricalContext,
    SeverityTransition,
)
from risk_orchestrator_agent.domain.models.incident_context import (
    IncidentContext,
    KGPath,
    SimilarIncident,
)
from risk_orchestrator_agent.domain.models.maintenance_context import MaintenanceContext
from risk_orchestrator_agent.domain.models.neighbor_zone_context import NeighborZoneContext
from risk_orchestrator_agent.domain.models.operational_timeline import (
    OperationalTimeline,
    TimelineEntry,
)
from risk_orchestrator_agent.domain.models.permit_context import PermitContext, PermitConflict
from risk_orchestrator_agent.domain.models.risk_context import (
    ConfidenceModel,
    ContextQuality,
    CorrelationMetadata,
    RiskContext,
    SiteContext,
    VersionMetadata,
)
from risk_orchestrator_agent.domain.models.sensor_context import Hazard, SensorContext
from risk_orchestrator_agent.domain.models.worker_context import ProximityAlert, WorkerContext
from risk_orchestrator_agent.domain.models.zone_context import Anomaly, ZoneContext


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _age(value: Age | None) -> dict | None:
    return {"seconds": value.duration.total_seconds()} if value else None


def _parse_age(value: dict | None) -> Age | None:
    return Age(duration=timedelta(seconds=value["seconds"])) if value else None


def encode(context: RiskContext) -> dict[str, Any]:
    """RiskContext -> JSON-safe dict."""

    def worker(w: WorkerContext) -> dict:
        return {
            "worker_id": w.worker_id,
            "safety_status": w.safety_status,
            "ppe_compliance": w.ppe_compliance,
            "ppe_violations": list(w.ppe_violations),
            "zone_clearance": w.zone_clearance,
            "proximity_alerts": [dataclasses.asdict(a) for a in w.proximity_alerts],
            "confidence": w.confidence.value,
            "analyzed_at": _dt(w.analyzed_at),
            "age": _age(w.age),
            "stale": w.stale,
        }

    def zone(z: ZoneContext) -> dict:
        return {
            "zone_id": z.zone_id,
            "site_id": z.site_id,
            "zone_state": z.zone_state,
            "risk_factors": list(z.risk_factors),
            "anomalies": [dataclasses.asdict(a) for a in z.anomalies],
            "worker_count": z.worker_count,
            "equipment_ids": list(z.equipment_ids),
            "confidence": z.confidence.value,
            "analyzed_at": _dt(z.analyzed_at),
            "age": _age(z.age),
            "stale": z.stale,
        }

    def equipment(e: EquipmentContext) -> dict:
        return {
            "equipment_id": e.equipment_id,
            "health_index": e.health_index,
            "failure_prediction": dataclasses.asdict(e.failure_prediction)
            if e.failure_prediction
            else None,
            "active_faults": list(e.active_faults),
            "overdue_tasks": list(e.overdue_tasks),
            "confidence": e.confidence.value,
            "analyzed_at": _dt(e.analyzed_at),
            "age": _age(e.age),
            "stale": e.stale,
        }

    def permit(p: PermitContext) -> dict:
        return {
            "permit_id": p.permit_id,
            "permit_risk_level": p.permit_risk_level,
            "conflicts": [dataclasses.asdict(c) for c in p.conflicts],
            "zone_compatibility": p.zone_compatibility,
            "zone_risk_at_issuance": p.zone_risk_at_issuance,
            "confidence": p.confidence.value,
            "analyzed_at": _dt(p.analyzed_at),
            "age": _age(p.age),
            "stale": p.stale,
        }

    def sensor(s: SensorContext) -> dict:
        return {
            "hazards": [dataclasses.asdict(h) for h in s.hazards],
            "evacuation_required": s.evacuation_required,
            "affected_zones": list(s.affected_zones),
            "confidence": s.confidence.value,
            "analyzed_at": _dt(s.analyzed_at),
            "age": _age(s.age),
            "stale": s.stale,
        }

    def incident(i: IncidentContext) -> dict:
        return {
            "similar_incidents": [
                {**dataclasses.asdict(s), "occurred_at": _dt(s.occurred_at)}
                for s in i.similar_incidents
            ],
            "historical_evidence": list(i.historical_evidence),
            "knowledge_graph_paths": [k.path for k in i.knowledge_graph_paths],
            "confidence": i.confidence.value,
            "analyzed_at": _dt(i.analyzed_at),
            "age": _age(i.age),
            "stale": i.stale,
        }

    def maintenance(m: MaintenanceContext) -> dict:
        return {
            "equipment_id": m.equipment_id,
            "health_index": m.health_index,
            "overdue_tasks": list(m.overdue_tasks),
            "confidence": m.confidence.value,
            "analyzed_at": _dt(m.analyzed_at),
            "age": _age(m.age),
            "stale": m.stale,
        }

    def historical(h: HistoricalContext) -> dict:
        return {
            "previous_severity": h.previous_severity,
            "previous_computed_at": _dt(h.previous_computed_at),
            "recent_transitions": [
                {**dataclasses.asdict(t), "transitioned_at": _dt(t.transitioned_at)}
                for t in h.recent_transitions
            ],
        }

    def neighbor(n: NeighborZoneContext) -> dict:
        return dataclasses.asdict(n)

    def timeline_entry(t: TimelineEntry) -> dict:
        return {**dataclasses.asdict(t), "analyzed_at": _dt(t.analyzed_at)}

    def evidence_item(e: EvidenceItem) -> dict:
        return {
            "evidence_id": e.evidence_id,
            "evidence_source": e.evidence_source,
            "evidence_type": e.evidence_type.value,
            "confidence": e.confidence,
            "timestamp": _dt(e.timestamp),
            "origin_agent": e.origin_agent,
            "supporting_event_ids": list(e.supporting_event_ids),
            "references": list(e.references),
        }

    def finding(f: CorrelationFinding) -> dict:
        return {
            "finding_id": f.finding_id,
            "correlation_type": f.correlation_type.value,
            "entity_refs": list(f.entity_refs),
            "strength": f.strength,
            "confidence": f.confidence,
            "summary": f.summary,
            "evidence_ids": list(f.evidence_ids),
            "degraded": f.degraded,
        }

    return {
        "zone_id": context.zone_id,
        "site_id": context.site_id,
        "snapshot_at": _dt(context.snapshot_at),
        "site": dataclasses.asdict(context.site) if context.site else None,
        "zone": zone(context.zone) if context.zone else None,
        "workers": [worker(w) for w in context.workers],
        "equipment": [equipment(e) for e in context.equipment],
        "permits": [permit(p) for p in context.permits],
        "sensor": sensor(context.sensor) if context.sensor else None,
        "incident": incident(context.incident) if context.incident else None,
        "maintenance": [maintenance(m) for m in context.maintenance],
        "historical": historical(context.historical) if context.historical else None,
        "neighbor_zones": [neighbor(n) for n in context.neighbor_zones],
        "operational_timeline": {
            "entries": [timeline_entry(e) for e in context.operational_timeline.entries],
            "window_seconds": context.operational_timeline.window.total_seconds(),
        },
        "evidence": {"items": [evidence_item(e) for e in context.evidence.items]},
        "correlation_findings": [finding(f) for f in context.correlation_findings],
        "confidence_model": dataclasses.asdict(context.confidence_model),
        "version_metadata": dataclasses.asdict(context.version_metadata),
        "correlation_metadata": dataclasses.asdict(context.correlation_metadata),
        "quality": dataclasses.asdict(context.quality),
    }


def decode(data: dict[str, Any]) -> RiskContext:
    """JSON-safe dict -> RiskContext."""

    zone = None
    if data.get("zone"):
        z = data["zone"]
        zone = ZoneContext(
            zone_id=z["zone_id"],
            site_id=z["site_id"],
            zone_state=z["zone_state"],
            risk_factors=tuple(z["risk_factors"]),
            anomalies=tuple(Anomaly(**a) for a in z["anomalies"]),
            worker_count=z["worker_count"],
            equipment_ids=tuple(z["equipment_ids"]),
            confidence=ConfidenceScore(z["confidence"]),
            analyzed_at=_parse_dt(z["analyzed_at"]),
            age=_parse_age(z["age"]),
            stale=z["stale"],
        )

    workers = tuple(
        WorkerContext(
            worker_id=w["worker_id"],
            safety_status=w["safety_status"],
            ppe_compliance=w["ppe_compliance"],
            ppe_violations=tuple(w["ppe_violations"]),
            zone_clearance=w["zone_clearance"],
            proximity_alerts=tuple(ProximityAlert(**a) for a in w["proximity_alerts"]),
            confidence=ConfidenceScore(w["confidence"]),
            analyzed_at=_parse_dt(w["analyzed_at"]),
            age=_parse_age(w["age"]),
            stale=w["stale"],
        )
        for w in data.get("workers", [])
    )

    equipment = tuple(
        EquipmentContext(
            equipment_id=e["equipment_id"],
            health_index=e["health_index"],
            failure_prediction=FailurePrediction(**e["failure_prediction"])
            if e["failure_prediction"]
            else None,
            active_faults=tuple(e["active_faults"]),
            overdue_tasks=tuple(e["overdue_tasks"]),
            confidence=ConfidenceScore(e["confidence"]),
            analyzed_at=_parse_dt(e["analyzed_at"]),
            age=_parse_age(e["age"]),
            stale=e["stale"],
        )
        for e in data.get("equipment", [])
    )

    permits = tuple(
        PermitContext(
            permit_id=p["permit_id"],
            permit_risk_level=p["permit_risk_level"],
            conflicts=tuple(PermitConflict(**c) for c in p["conflicts"]),
            zone_compatibility=p["zone_compatibility"],
            zone_risk_at_issuance=p["zone_risk_at_issuance"],
            confidence=ConfidenceScore(p["confidence"]),
            analyzed_at=_parse_dt(p["analyzed_at"]),
            age=_parse_age(p["age"]),
            stale=p["stale"],
        )
        for p in data.get("permits", [])
    )

    sensor = None
    if data.get("sensor"):
        s = data["sensor"]
        sensor = SensorContext(
            hazards=tuple(Hazard(**h) for h in s["hazards"]),
            evacuation_required=s["evacuation_required"],
            affected_zones=tuple(s["affected_zones"]),
            confidence=ConfidenceScore(s["confidence"]),
            analyzed_at=_parse_dt(s["analyzed_at"]),
            age=_parse_age(s["age"]),
            stale=s["stale"],
        )

    incident = None
    if data.get("incident"):
        i = data["incident"]
        incident = IncidentContext(
            similar_incidents=tuple(
                SimilarIncident(**{**si, "occurred_at": _parse_dt(si["occurred_at"])})
                for si in i["similar_incidents"]
            ),
            historical_evidence=tuple(i["historical_evidence"]),
            knowledge_graph_paths=tuple(KGPath(p) for p in i["knowledge_graph_paths"]),
            confidence=ConfidenceScore(i["confidence"]),
            analyzed_at=_parse_dt(i["analyzed_at"]),
            age=_parse_age(i["age"]),
            stale=i["stale"],
        )

    maintenance = tuple(
        MaintenanceContext(
            equipment_id=m["equipment_id"],
            health_index=m["health_index"],
            overdue_tasks=tuple(m["overdue_tasks"]),
            confidence=ConfidenceScore(m["confidence"]),
            analyzed_at=_parse_dt(m["analyzed_at"]),
            age=_parse_age(m["age"]),
            stale=m["stale"],
        )
        for m in data.get("maintenance", [])
    )

    historical = None
    if data.get("historical"):
        h = data["historical"]
        historical = HistoricalContext(
            previous_severity=h["previous_severity"],
            previous_computed_at=_parse_dt(h["previous_computed_at"]),
            recent_transitions=tuple(
                SeverityTransition(**{**t, "transitioned_at": _parse_dt(t["transitioned_at"])})
                for t in h["recent_transitions"]
            ),
        )

    neighbor_zones = tuple(NeighborZoneContext(**n) for n in data.get("neighbor_zones", []))

    timeline_data = data.get("operational_timeline", {"entries": [], "window_seconds": 3600})
    operational_timeline = OperationalTimeline(
        entries=tuple(
            TimelineEntry(**{**e, "analyzed_at": _parse_dt(e["analyzed_at"])})
            for e in timeline_data["entries"]
        ),
        window=timedelta(seconds=timeline_data.get("window_seconds", 3600)),
    )

    evidence = EvidenceCollection(
        items=tuple(
            EvidenceItem(
                **{
                    **e,
                    "evidence_type": EvidenceType(e["evidence_type"]),
                    "timestamp": _parse_dt(e["timestamp"]),
                    "supporting_event_ids": tuple(e["supporting_event_ids"]),
                    "references": tuple(e["references"]),
                }
            )
            for e in data.get("evidence", {}).get("items", [])
        )
    )

    correlation_findings = tuple(
        CorrelationFinding(
            **{
                **f,
                "correlation_type": CorrelationType(f["correlation_type"]),
                "entity_refs": tuple(f["entity_refs"]),
                "evidence_ids": tuple(f["evidence_ids"]),
            }
        )
        for f in data.get("correlation_findings", [])
    )

    site_data = data.get("site")
    site = (
        SiteContext(
            site_id=site_data["site_id"],
            overall_state=site_data.get("overall_state", "normal"),
            total_workers=site_data.get("total_workers", 0),
            active_permits=site_data.get("active_permits", 0),
            active_zone_ids=tuple(site_data.get("active_zone_ids", ())),
        )
        if site_data
        else None
    )

    cm_data = data["correlation_metadata"]
    correlation_metadata = CorrelationMetadata(
        correlation_id=cm_data["correlation_id"],
        causation_id=cm_data.get("causation_id"),
        input_event_ids=tuple(cm_data.get("input_event_ids", ())),
    )

    return RiskContext(
        zone_id=data["zone_id"],
        site_id=data["site_id"],
        snapshot_at=_parse_dt(data["snapshot_at"]),
        site=site,
        zone=zone,
        workers=workers,
        equipment=equipment,
        permits=permits,
        sensor=sensor,
        incident=incident,
        maintenance=maintenance,
        historical=historical,
        neighbor_zones=neighbor_zones,
        operational_timeline=operational_timeline,
        evidence=evidence,
        correlation_findings=correlation_findings,
        confidence_model=ConfidenceModel(
            aggregate_confidence=data["confidence_model"]["aggregate_confidence"],
            per_domain_confidence=dict(data["confidence_model"].get("per_domain_confidence", {})),
            derivation_method=data["confidence_model"].get(
                "derivation_method", "completeness_weighted"
            ),
        ),
        version_metadata=VersionMetadata(**data["version_metadata"]),
        correlation_metadata=correlation_metadata,
        quality=ContextQuality(
            completeness=data["quality"]["completeness"],
            consistency=data["quality"].get("consistency", 1.0),
            has_stale_domains=data["quality"].get("has_stale_domains", False),
            missing_domains=tuple(data["quality"].get("missing_domains", ())),
            stale_domains=tuple(data["quality"].get("stale_domains", ())),
            contested_fields=tuple(data["quality"].get("contested_fields", ())),
            corrupted_fields=tuple(data["quality"].get("corrupted_fields", ())),
            topology_unavailable=data["quality"].get("topology_unavailable", False),
        ),
    )
