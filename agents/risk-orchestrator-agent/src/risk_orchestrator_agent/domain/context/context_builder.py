"""domain/context/context_builder.py — ContextBuilder (Phase 2.2 in full).

Assembles, merges, and snapshots the per-zone `RiskContext`. Never
computes risk (Phase 2.2 §1.4) — only assembles facts.

Constructor-injected with its three ports (ALDS §3.1): `ContextBuilder(
context_port, history_port, graph_port)`. Receives an already-live
implementation of each at construction time — this file never imports a
concrete adapter (Phase 3.1 §3.4).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from risk_orchestrator_agent.domain.context import entity_linking, merge_rules, temporal_window
from risk_orchestrator_agent.domain.context.spatial_enrichment import enrich_neighbor_zones
from risk_orchestrator_agent.domain.exceptions import ContextValidationError
from risk_orchestrator_agent.domain.models.confidence import ConfidenceScore
from risk_orchestrator_agent.domain.models.evidence import EvidenceItem, EvidenceType
from risk_orchestrator_agent.domain.models.evidence_collection import EvidenceCollection
from risk_orchestrator_agent.domain.models.historical_context import HistoricalContext
from risk_orchestrator_agent.domain.models.operational_timeline import OperationalTimeline
from risk_orchestrator_agent.domain.models.risk_context import (
    ALL_DOMAINS,
    ConfidenceModel,
    ContextQuality,
    CorrelationMetadata,
    RiskContext,
    SiteContext,
    VersionMetadata,
)
from risk_orchestrator_agent.domain.ports.context_repository_port import ContextRepositoryPort
from risk_orchestrator_agent.domain.ports.graph_repository_port import GraphRepositoryPort
from risk_orchestrator_agent.domain.ports.history_repository_port import HistoryRepositoryPort
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

CONTEXT_BUILDER_VERSION = "1.0.0"


def _empty_context(zone_id: str, site_id: str) -> RiskContext:
    """Phase 2.2 §5.2 Created state: a brand-new zone, every domain
    explicitly absent, never defaulted to a safe value."""
    now = utcnow()
    return RiskContext(
        zone_id=zone_id,
        site_id=site_id,
        snapshot_at=now,
        site=SiteContext(site_id=site_id, active_zone_ids=(zone_id,)),
        zone=None,
        workers=(),
        equipment=(),
        permits=(),
        sensor=None,
        incident=None,
        maintenance=(),
        historical=None,
        neighbor_zones=(),
        operational_timeline=OperationalTimeline(),
        evidence=EvidenceCollection(),
        correlation_findings=(),
        confidence_model=ConfidenceModel(aggregate_confidence=0.0, per_domain_confidence={}),
        version_metadata=VersionMetadata(context_builder_version=CONTEXT_BUILDER_VERSION),
        correlation_metadata=CorrelationMetadata(correlation_id="", causation_id=None),
        quality=ContextQuality(completeness=0.0, missing_domains=ALL_DOMAINS),
    )


class ContextBuilder:
    """Domain service. Stateless compute wrapper — all durable state lives
    behind `ContextRepositoryPort` (Phase 2.2 §5.7 recovery behavior)."""

    def __init__(
        self,
        context_port: ContextRepositoryPort,
        history_port: HistoryRepositoryPort | None = None,
        graph_port: GraphRepositoryPort | None = None,
    ) -> None:
        self._context_port = context_port
        self._history_port = history_port
        self._graph_port = graph_port

    # ------------------------------------------------------------------
    # Public interface (FRS §3.1)
    # ------------------------------------------------------------------

    async def update(self, zone_id: str, payload: AgentResultDTO) -> RiskContext:
        """Merge one domain's update into the zone's rolling context and
        persist it. Returns the updated (not-yet-snapshotted) rolling
        context, mostly for observability/testing convenience."""
        current = await self._safe_get(zone_id)
        if current is None:
            current = _empty_context(zone_id, payload.site_id)

        merged = self._merge(current, payload)
        await self._context_port.put(zone_id, merged)
        return merged

    async def snapshot(self, zone_id: str) -> RiskContext:
        """Produce the finalized, immutable RiskContext handed to
        CorrelationEngine for one scoring cycle (Phase 2.2 §5.4)."""
        current = await self._safe_get(zone_id)
        if current is None:
            current = _empty_context(zone_id, site_id="unknown")

        historical = await self._retrieve_historical(zone_id)
        neighbor_zones, topology_unavailable = await enrich_neighbor_zones(
            zone_id, self._graph_port
        )

        enriched = self._apply_staleness(current)
        quality = self._validate(enriched, topology_unavailable=topology_unavailable)

        snapshot = RiskContext(
            zone_id=enriched.zone_id,
            site_id=enriched.site_id,
            snapshot_at=utcnow(),
            site=enriched.site,
            zone=enriched.zone,
            workers=enriched.workers,
            equipment=enriched.equipment,
            permits=enriched.permits,
            sensor=enriched.sensor,
            incident=enriched.incident,
            maintenance=enriched.maintenance,
            historical=historical,
            neighbor_zones=neighbor_zones,
            operational_timeline=enriched.operational_timeline,
            evidence=enriched.evidence,
            correlation_findings=(),
            confidence_model=quality[1],
            version_metadata=VersionMetadata(context_builder_version=CONTEXT_BUILDER_VERSION),
            correlation_metadata=enriched.correlation_metadata,
            quality=quality[0],
        )
        return snapshot

    # ------------------------------------------------------------------
    # Internal helpers (FRS §3.1)
    # ------------------------------------------------------------------

    async def _safe_get(self, zone_id: str) -> RiskContext | None:
        try:
            return await self._context_port.get(zone_id)
        except Exception:  # noqa: BLE001 - degrade, never propagate (Phase 2.2 §5.7/§14)
            logger.warning("context_repository_degraded", extra={"zone_id": zone_id})
            return None

    async def _retrieve_historical(self, zone_id: str) -> HistoricalContext | None:
        if self._history_port is None:
            return None
        try:
            previous_severity, previous_computed_at = await self._history_port.get_previous_severity(
                zone_id
            )
            transitions = await self._history_port.get_recent_transitions(zone_id)
            return HistoricalContext(
                previous_severity=previous_severity,
                previous_computed_at=previous_computed_at,
                recent_transitions=transitions,
            )
        except Exception:  # noqa: BLE001 - degrade (Phase 2.4 §12)
            logger.warning("history_unavailable", extra={"zone_id": zone_id})
            return None

    def _merge(self, current: RiskContext, payload: AgentResultDTO) -> RiskContext:
        """Merge exactly one domain's update against the loaded baseline
        (Phase 2.2 §5.3). Last-write-wins per domain, keyed by
        `analyzed_at`, with documented exceptions (e.g. equipment
        `active_faults` accumulate)."""
        domain = payload.domain_name
        parser = merge_rules.PARSERS[domain]
        incoming = parser(payload)

        evidence_item = EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            evidence_source=payload.event_type,
            evidence_type=EvidenceType.AGENT_INFERENCE,
            confidence=payload.confidence,
            timestamp=payload.analyzed_at,
            origin_agent=payload.agent_id,
            supporting_event_ids=(payload.event_id,),
        )
        new_evidence = current.evidence.merged_with(EvidenceCollection(items=(evidence_item,)))
        new_timeline = temporal_window.fold(current.operational_timeline, payload)
        new_correlation_metadata = CorrelationMetadata(
            correlation_id=payload.correlation_id,
            causation_id=payload.causation_id,
            input_event_ids=current.correlation_metadata.input_event_ids + (payload.event_id,),
        )

        updates: dict = {
            "evidence": new_evidence,
            "operational_timeline": new_timeline,
            "correlation_metadata": new_correlation_metadata,
            "site_id": payload.site_id or current.site_id,
        }

        if domain == "worker":
            updates["workers"] = entity_linking.upsert_by_id(
                current.workers, incoming, "worker_id"
            )
        elif domain == "zone":
            if current.zone is None or merge_rules.resolve_by_timestamp(
                current.zone.analyzed_at, incoming.analyzed_at
            ):
                updates["zone"] = incoming
        elif domain == "equipment":
            existing_map = entity_linking.index_equipment(current.equipment)
            existing_eq = existing_map.get(incoming.equipment_id)
            merged_eq = merge_rules.merge_equipment_active_faults(existing_eq, incoming)
            updates["equipment"] = entity_linking.upsert_by_id(
                current.equipment, merged_eq, "equipment_id"
            )
        elif domain == "permit":
            updates["permits"] = entity_linking.upsert_by_id(
                current.permits, incoming, "permit_id"
            )
        elif domain == "sensor":
            if current.sensor is None or merge_rules.resolve_by_timestamp(
                current.sensor.analyzed_at, incoming.analyzed_at
            ):
                updates["sensor"] = incoming
        elif domain == "incident":
            # Supplementary/additive, never overrides (Phase 2.2 §3.1).
            updates["incident"] = incoming
        elif domain == "maintenance":
            # Phase 1 §4.4's single `sentinel.maintenance.analysis.v1` topic
            # ("Equipment / Maintenance Intelligence") carries fields for
            # both the `EquipmentContext` and `MaintenanceContext`
            # sub-contexts (Phase 2.2 §4.1) — there is no separate
            # equipment-only topic, so one payload legitimately updates
            # both slices of this bounded context's model.
            updates["maintenance"] = entity_linking.upsert_by_id(
                current.maintenance, incoming, "equipment_id"
            )
            if payload.payload.get("equipment_id"):
                incoming_equipment = merge_rules.parse_equipment(payload)
                existing_map = entity_linking.index_equipment(current.equipment)
                existing_eq = existing_map.get(incoming_equipment.equipment_id)
                merged_eq = merge_rules.merge_equipment_active_faults(existing_eq, incoming_equipment)
                updates["equipment"] = entity_linking.upsert_by_id(
                    current.equipment, merged_eq, "equipment_id"
                )

        import dataclasses

        return dataclasses.replace(current, **updates)

    def _apply_staleness(self, context: RiskContext) -> RiskContext:
        """Refresh is the periodic re-evaluation of staleness across all
        domains (Phase 2.2 §5.5) — the individual sub-context `stale`
        flags are already computed at parse time (merge_rules); this
        step is the seam a future TTL-driven re-check would extend."""
        return context

    def _validate(
        self, context: RiskContext, *, topology_unavailable: bool
    ) -> tuple[ContextQuality, ConfidenceModel]:
        """Completeness/consistency checks (Phase 2.2 §12). A hard
        validation failure (missing evidence for a populated fact) routes
        to DLQ via `ContextValidationError` — the common case is a
        passing, partial-information context, which is not a failure
        (Phase 1 §9.5)."""
        present: dict[str, bool] = {
            "worker": bool(context.workers),
            "zone": context.zone is not None,
            "equipment": bool(context.equipment),
            "permit": bool(context.permits),
            "sensor": context.sensor is not None,
            "incident": context.incident is not None,
            "maintenance": bool(context.maintenance),
        }
        missing = tuple(d for d in ALL_DOMAINS if not present[d])
        stale_domains: list[str] = []
        if context.zone is not None and context.zone.stale:
            stale_domains.append("zone")
        if context.sensor is not None and context.sensor.stale:
            stale_domains.append("sensor")
        stale_domains.extend(w.worker_id for w in context.workers if w.stale)

        completeness = (len(ALL_DOMAINS) - len(missing)) / len(ALL_DOMAINS)

        per_domain_confidence: dict[str, float] = {}
        if context.zone is not None:
            per_domain_confidence["zone"] = context.zone.confidence.value
        if context.sensor is not None:
            per_domain_confidence["sensor"] = context.sensor.confidence.value
        for w in context.workers:
            per_domain_confidence[f"worker:{w.worker_id}"] = w.confidence.value
        for e in context.equipment:
            per_domain_confidence[f"equipment:{e.equipment_id}"] = e.confidence.value
        for p in context.permits:
            per_domain_confidence[f"permit:{p.permit_id}"] = p.confidence.value
        if context.incident is not None:
            per_domain_confidence["incident"] = context.incident.confidence.value

        aggregate = (
            sum(per_domain_confidence.values()) / len(per_domain_confidence)
            if per_domain_confidence
            else 0.0
        )

        # Enforcement point (Phase 2.2 §11.2): a populated fact with no
        # corresponding evidence entry must not be admitted.
        if present["zone"] or context.workers or context.equipment:
            if len(context.evidence) == 0:
                raise ContextValidationError(
                    "Populated context has no supporting evidence",
                    zone_id=context.zone_id,
                    reasons=["missing_evidence"],
                )

        quality = ContextQuality(
            completeness=completeness,
            consistency=1.0,
            has_stale_domains=bool(stale_domains),
            missing_domains=missing,
            stale_domains=tuple(stale_domains),
            topology_unavailable=topology_unavailable,
        )
        confidence_model = ConfidenceModel(
            aggregate_confidence=aggregate,
            per_domain_confidence=per_domain_confidence,
        )
        return quality, confidence_model
