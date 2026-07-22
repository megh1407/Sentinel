"""domain/correlation/correlation_types.py — the correlation-type catalog
(Phase 2.3 §4.1), realized for this implementation phase's scope:
relationship discovery only, no rule evaluation.

Each function returns zero or more `CorrelationFinding`s. Structural
computation only (Phase 2.3 §4.3) — never a risk judgment.
"""

from __future__ import annotations

import uuid

from risk_orchestrator_agent.domain.models.correlation_finding import (
    CorrelationFinding,
    CorrelationType,
)
from risk_orchestrator_agent.domain.models.risk_context import RiskContext


def _new_id() -> str:
    return str(uuid.uuid4())


def _combined_confidence(*confidences: float) -> float:
    """Minimum-anchored, conservative combination (Phase 2.3 §10.2) — one
    weak or stale contributing fact cannot be diluted into an
    artificially confident correlation."""
    values = [c for c in confidences if c is not None]
    return min(values) if values else 0.0


def worker_zone(context: RiskContext) -> list[CorrelationFinding]:
    if context.zone is None:
        return []
    findings = []
    for worker in context.workers:
        strength = 1.0 if worker.zone_clearance else 0.6
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.WORKER_ZONE,
                entity_refs=(worker.worker_id, context.zone.zone_id),
                strength=strength,
                confidence=_combined_confidence(worker.confidence.value, context.zone.confidence.value),
                summary=f"Worker {worker.worker_id} located in zone {context.zone.zone_id}",
            )
        )
    return findings


def worker_permit(context: RiskContext) -> list[CorrelationFinding]:
    """Worker scoped to a permit's authorized zone/task (Phase 2.3 §4.1).
    Without an explicit worker->permit reference in the wire payload,
    this is inferred structurally: any worker present in the zone is
    linked to every currently-active permit scoped to that same zone."""
    findings = []
    for worker in context.workers:
        for permit in context.permits:
            findings.append(
                CorrelationFinding(
                    finding_id=_new_id(),
                    correlation_type=CorrelationType.WORKER_PERMIT,
                    entity_refs=(worker.worker_id, permit.permit_id),
                    strength=0.7,
                    confidence=_combined_confidence(worker.confidence.value, permit.confidence.value),
                    summary=f"Worker {worker.worker_id} co-located with active permit {permit.permit_id}",
                )
            )
    return findings


def worker_equipment(context: RiskContext) -> list[CorrelationFinding]:
    findings = []
    for worker in context.workers:
        for alert in worker.proximity_alerts:
            findings.append(
                CorrelationFinding(
                    finding_id=_new_id(),
                    correlation_type=CorrelationType.WORKER_EQUIPMENT,
                    entity_refs=(worker.worker_id,),
                    strength=1.0 if alert.within_hazard_radius else 0.4,
                    confidence=worker.confidence.value,
                    summary=(
                        f"Worker {worker.worker_id} at {alert.distance_m}m from "
                        f"{alert.hazard_type} (safe distance {alert.safe_distance_m}m)"
                    ),
                )
            )
    return findings


def zone_equipment(context: RiskContext) -> list[CorrelationFinding]:
    if context.zone is None:
        return []
    findings = []
    for equipment_id in context.zone.equipment_ids:
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.EQUIPMENT_SENSOR,
                entity_refs=(context.zone.zone_id, equipment_id),
                strength=1.0,
                confidence=context.zone.confidence.value,
                summary=f"Equipment {equipment_id} located in zone {context.zone.zone_id}",
            )
        )
    return findings


def equipment_maintenance(context: RiskContext) -> list[CorrelationFinding]:
    findings = []
    equipment_by_id = {e.equipment_id: e for e in context.equipment}
    for maint in context.maintenance:
        if not maint.overdue_tasks:
            continue
        equipment = equipment_by_id.get(maint.equipment_id)
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.EQUIPMENT_MAINTENANCE,
                entity_refs=(maint.equipment_id,),
                strength=0.8,
                confidence=_combined_confidence(
                    maint.confidence.value, equipment.confidence.value if equipment else None
                ),
                summary=f"Equipment {maint.equipment_id} has overdue maintenance: {list(maint.overdue_tasks)}",
            )
        )
    return findings


def permit_zone(context: RiskContext) -> list[CorrelationFinding]:
    if context.zone is None:
        return []
    findings = []
    for permit in context.permits:
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.PERMIT_ZONE,
                entity_refs=(permit.permit_id, context.zone.zone_id),
                strength=1.0 if permit.zone_compatibility else 0.5,
                confidence=_combined_confidence(permit.confidence.value, context.zone.confidence.value),
                summary=f"Permit {permit.permit_id} active in zone {context.zone.zone_id}",
            )
        )
    return findings


def permit_equipment(context: RiskContext) -> list[CorrelationFinding]:
    """Permit scope referencing specific equipment (Phase 2.3 §4.1) —
    inferred structurally via shared zone equipment_ids in this
    implementation phase, since the wire payload carries no direct
    permit->equipment reference yet."""
    if context.zone is None:
        return []
    findings = []
    for permit in context.permits:
        for equipment_id in context.zone.equipment_ids:
            findings.append(
                CorrelationFinding(
                    finding_id=_new_id(),
                    correlation_type=CorrelationType.PERMIT_EQUIPMENT,
                    entity_refs=(permit.permit_id, equipment_id),
                    strength=0.5,
                    confidence=permit.confidence.value,
                    summary=f"Permit {permit.permit_id} co-scoped with equipment {equipment_id}",
                )
            )
    return findings


def environment_zone(context: RiskContext) -> list[CorrelationFinding]:
    if context.zone is None or context.sensor is None:
        return []
    findings = []
    for hazard in context.sensor.hazards:
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.ENVIRONMENT_ZONE,
                entity_refs=(context.zone.zone_id,),
                strength=1.0 if hazard.threshold_breach else 0.5,
                confidence=_combined_confidence(context.sensor.confidence.value, context.zone.confidence.value),
                summary=(
                    f"Hazard {hazard.hazard_type} ({hazard.trend}) measured in zone "
                    f"{context.zone.zone_id}: {hazard.measured_value}{hazard.unit}"
                ),
            )
        )
    return findings


def incident_worker(context: RiskContext) -> list[CorrelationFinding]:
    if context.incident is None:
        return []
    findings = []
    for similar in context.incident.similar_incidents:
        for worker in context.workers:
            findings.append(
                CorrelationFinding(
                    finding_id=_new_id(),
                    correlation_type=CorrelationType.INCIDENT_WORKER,
                    entity_refs=(similar.incident_id, worker.worker_id),
                    strength=similar.similarity,
                    confidence=_combined_confidence(context.incident.confidence.value, worker.confidence.value),
                    summary=f"Historical incident {similar.incident_id} ({similar.incident_type}) precedent for present worker {worker.worker_id}",
                )
            )
    return findings


def incident_equipment(context: RiskContext) -> list[CorrelationFinding]:
    if context.incident is None:
        return []
    findings = []
    for similar in context.incident.similar_incidents:
        for equipment in context.equipment:
            findings.append(
                CorrelationFinding(
                    finding_id=_new_id(),
                    correlation_type=CorrelationType.INCIDENT_EQUIPMENT,
                    entity_refs=(similar.incident_id, equipment.equipment_id),
                    strength=similar.similarity,
                    confidence=_combined_confidence(context.incident.confidence.value, equipment.confidence.value),
                    summary=f"Historical incident {similar.incident_id} precedent for present equipment {equipment.equipment_id}",
                )
            )
    return findings


def incident_historical(context: RiskContext) -> list[CorrelationFinding]:
    """Historical Pattern Correlation (Phase 2.3 §2): links the zone's own
    recent severity trajectory to the current situation."""
    if context.historical is None or not context.historical.recent_transitions:
        return []
    return [
        CorrelationFinding(
            finding_id=_new_id(),
            correlation_type=CorrelationType.INCIDENT_HISTORICAL,
            entity_refs=(context.zone_id,),
            strength=0.6,
            confidence=0.7,
            summary=(
                f"Zone {context.zone_id} has {len(context.historical.recent_transitions)} "
                "recent severity transitions on record"
            ),
        )
    ]


def zone_neighbor_zone(context: RiskContext) -> list[CorrelationFinding]:
    if context.zone is None:
        return []
    findings = []
    for neighbor in context.neighbor_zones:
        findings.append(
            CorrelationFinding(
                finding_id=_new_id(),
                correlation_type=CorrelationType.ZONE_NEIGHBOR_ZONE,
                entity_refs=(context.zone.zone_id, neighbor.neighbor_zone_id),
                strength=0.5,
                confidence=context.zone.confidence.value,
                summary=f"Zone {context.zone.zone_id} is {neighbor.relationship_type} of {neighbor.neighbor_zone_id}",
                degraded=context.quality.topology_unavailable,
            )
        )
    return findings
