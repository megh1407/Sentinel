"""domain/context/temporal_window.py — OperationalTimeline logic
(Phase 2.2 §9).

Builds a `TimelineEntry` from an inbound `AgentResultDTO` and folds it
into the zone's `OperationalTimeline`, ordered strictly by `analyzed_at`
(Phase 2.2 §9.4), never by Kafka arrival order.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.models.operational_timeline import (
    OperationalTimeline,
    TimelineEntry,
)
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.utils.time_utils import utcnow


def _primary_field(domain: str, payload: dict) -> tuple[str, str]:
    """Picks the single most trend-relevant field per domain for the
    lightweight timeline summary (Phase 2.2 §9.2). Every field of every
    payload is still retrievable via EvidenceCollection/raw context —
    this is only the fast trend-detection projection."""
    candidates = {
        "sensor": ("hazard_measured_value", lambda p: (p.get("hazards") or [{}])[0].get("measured_value")),
        "zone": ("risk_score", lambda p: p.get("risk_score")),
        "worker": ("ppe_compliance", lambda p: p.get("ppe_compliance")),
        "equipment": ("health_index", lambda p: p.get("health_index")),
        "permit": ("permit_risk_level", lambda p: p.get("permit_risk_level")),
        "incident": ("risk_score", lambda p: p.get("risk_score")),
        "maintenance": ("health_index", lambda p: p.get("health_index")),
    }
    field_name, extractor = candidates.get(domain, ("value", lambda p: None))
    value = extractor(payload)
    return field_name, "" if value is None else str(value)


def build_entry(dto: AgentResultDTO) -> TimelineEntry:
    field_name, value = _primary_field(dto.domain_name, dto.payload)
    return TimelineEntry(
        domain=dto.domain_name,
        field=field_name,
        value=value,
        analyzed_at=dto.analyzed_at,
        event_id=dto.event_id,
    )


def fold(timeline: OperationalTimeline, dto: AgentResultDTO) -> OperationalTimeline:
    entry = build_entry(dto)
    return timeline.with_entry(entry, now=utcnow())
