"""domain/context/entity_linking.py — Entity Linking (Phase 2.2 §2).

Resolves the same real-world entity (a specific worker, permit, or
equipment unit) referenced by different agents into one canonical
identity. In this implementation phase, agent payloads already use
platform-canonical IDs (`worker_id`, `permit_id`, `equipment_id`) at the
wire-format boundary, so linking is an identity/index operation — this
module is the single named seam future fuzzy-linking logic (e.g. an
upstream agent using a locally-scoped alias) attaches to, per Phase 2.2
§17's additive-extension pattern.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.models.equipment_context import EquipmentContext
from risk_orchestrator_agent.domain.models.permit_context import PermitContext
from risk_orchestrator_agent.domain.models.worker_context import WorkerContext


def index_workers(workers: tuple[WorkerContext, ...]) -> dict[str, WorkerContext]:
    return {w.worker_id: w for w in workers}


def index_equipment(equipment: tuple[EquipmentContext, ...]) -> dict[str, EquipmentContext]:
    return {e.equipment_id: e for e in equipment}


def index_permits(permits: tuple[PermitContext, ...]) -> dict[str, PermitContext]:
    return {p.permit_id: p for p in permits}


def upsert_by_id(existing: tuple, incoming, id_attr: str) -> tuple:
    """Canonical-identity upsert: replaces the entry sharing `incoming`'s
    ID, or appends if this is a newly-linked entity for the zone."""
    incoming_id = getattr(incoming, id_attr)
    kept = tuple(item for item in existing if getattr(item, id_attr) != incoming_id)
    return kept + (incoming,)
