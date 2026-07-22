"""domain/decision/site_synthesizer.py — SiteRiskSynthesizer.

Closes the gap flagged in docs/RECONCILIATION_REPORT.md §6 gap #1: a
genuine multi-zone view, reasoning across several zones' already-computed
`ZoneAssessmentResult`s at once, rather than one zone's neighbor-aware
but still single-zone view. This is still not the full site-wide
`SiteState` aggregate that report describes (this synthesizer only sees
whichever zones' results it's handed by the caller for one decision
cycle — see `application/site_orchestration.py` — not a live, continuously
maintained graph of the entire site); it is, however, a real
multiple-zones-at-once computation, which nothing in either source
snapshot had.

**Two fields populated conservatively, not fabricated** — flagged
directly rather than glossed over:

- `PermitRiskEntry.permit_type`: `domain/models/permit_context.
  PermitContext` has no `permit_type` field (no "HOT_WORK" vocabulary
  exists upstream) — always `None` here until that field exists.
- `IncidentContextSummary.active_incidents`: `domain/models/
  incident_context.IncidentContext` models vector-similarity *historical*
  incidents (`similar_incidents`), not currently active ones — always
  `()` here. `emergency_detected`/`emergency_type` are populated from the
  live decision, not from this (nonexistent) active-incidents feed.

Combination method for `overall_risk_score`/`systemic_risk`: noisy-OR
across every zone's own `GlobalRiskScore.value` (each of which already
embeds that zone's local + interaction risk). Same rationale as
`decision_engine.py`: guarantees the systemic score is never lower than
any single zone's own already-elevated score, and compounds smoothly as
more zones carry real risk — without an arbitrary cap or a sum that can
double-count zones that already reference each other via
`interaction_risks`.
"""

from __future__ import annotations

from risk_orchestrator_agent.domain.decision.decision_engine import classify_score
from risk_orchestrator_agent.domain.enums import RuleCategory
from risk_orchestrator_agent.domain.models.risk_decision_package import (
    EmergencyDecision,
    IncidentContextSummary,
    InteractionRiskEntry,
    PermitRiskEntry,
    Provenance,
    RiskAssessmentSummary,
    RiskBreakdown,
    ZoneRiskSummary,
)
from risk_orchestrator_agent.domain.models.zone_assessment_result import ZoneAssessmentResult


def _noisy_or(scores_0_to_100: list[float]) -> float:
    if not scores_0_to_100:
        return 0.0
    remaining = 1.0
    for s in scores_0_to_100:
        remaining *= 1.0 - min(1.0, max(0.0, s / 100.0))
    return round((1.0 - remaining) * 100.0, 2)


def _category_score(results: list[ZoneAssessmentResult], category: RuleCategory) -> float:
    contributions = []
    for result in results:
        for finding in result.findings:
            if finding.category == category:
                contributions.append(finding.weight * finding.confidence * 100.0)
    return _noisy_or(contributions)


class SiteRiskSynthesizer:
    """Stateless domain service."""

    def synthesize(self, results: list[ZoneAssessmentResult]) -> tuple[
        RiskAssessmentSummary,
        tuple[ZoneRiskSummary, ...],
        tuple[InteractionRiskEntry, ...],
        tuple[PermitRiskEntry, ...],
        IncidentContextSummary,
        RiskBreakdown,
        tuple[str, ...],
        EmergencyDecision,
        Provenance,
    ]:
        if not results:
            raise ValueError("SiteRiskSynthesizer.synthesize() requires at least one zone result")

        zone_risks = tuple(
            ZoneRiskSummary(
                zone_id=r.context.zone_id,
                risk_score=r.global_score.value,
                risk_level=r.severity.value.upper(),
                risk_factors=tuple(f.description for f in r.findings),
            )
            for r in results
        )

        interacting_results = [r for r in results if r.interaction.score > 0]
        interaction_risks = tuple(
            InteractionRiskEntry(
                type="CROSS_ZONE_ESCALATION",
                zones=(r.context.zone_id,) + tuple(step.to_zone_id for step in r.interaction.propagation_paths),
                severity=classify_score(r.interaction.score).value.upper(),
                reason="; ".join(r.interaction.explanation) or "Cross-zone interaction detected",
            )
            for r in interacting_results
        )

        permit_risks = tuple(
            PermitRiskEntry(
                permit_id=finding.entity_refs[0] if finding.entity_refs else "UNKNOWN_PERMIT",
                permit_type=None,  # not modeled upstream — see module docstring
                status="CONFLICTING" if finding.rule_id == "permit.conflict" else "ZONE_INCOMPATIBLE",
                risk_contribution=finding.priority.value.upper(),
                reason=finding.description,
            )
            for r in results
            for finding in r.findings
            if finding.rule_id in ("permit.conflict", "permit.zone_incompatible")
        )

        zone_scores = [r.global_score.value for r in results]
        systemic_risk = _noisy_or(zone_scores)
        local_risk = max((r.local.score for r in results), default=0.0)
        cross_zone_risk = _noisy_or([r.interaction.score for r in results])
        permit_conflict_risk = _category_score(results, RuleCategory.PERMIT)
        environmental_risk = _category_score(results, RuleCategory.ENVIRONMENTAL)
        human_exposure_risk = _category_score(results, RuleCategory.WORKER_SAFETY)

        risk_breakdown = RiskBreakdown(
            local_risk=local_risk,
            cross_zone_risk=cross_zone_risk,
            permit_conflict_risk=permit_conflict_risk,
            environmental_risk=environmental_risk,
            human_exposure_risk=human_exposure_risk,
            systemic_risk=systemic_risk,
        )

        overall_level = classify_score(systemic_risk)
        zones_with_risk = [r for r in results if r.local.score > 10.0 or r.interaction.score > 0]
        if len(interacting_results) >= 2 or (interacting_results and len(zones_with_risk) >= 3):
            risk_scope = "SYSTEMIC"
        elif len(zones_with_risk) >= 2:
            risk_scope = "MULTI_ZONE"
        else:
            risk_scope = "LOCALIZED"

        affected_zones = tuple(r.context.zone_id for r in zones_with_risk) or tuple(
            r.context.zone_id for r in results
        )

        confidence = round(sum(r.context.confidence_model.aggregate_confidence for r in results) / len(results), 3)

        risk_assessment = RiskAssessmentSummary(
            overall_risk_level=overall_level.value.upper(),
            overall_risk_score=systemic_risk,
            confidence=confidence,
            risk_scope=risk_scope,
            affected_zones=affected_zones,
        )

        is_emergency = any(r.escalation_required for r in results) or risk_scope == "SYSTEMIC"
        triggered_by = tuple(
            dict.fromkeys(
                f.rule_id.upper()
                for r in results
                if r.escalation_required or r.interaction.score > 0
                for f in r.findings
                if f.priority.value in ("critical", "high")
            )
        )
        if risk_scope == "SYSTEMIC":
            triggered_by = triggered_by + ("CROSS_ZONE_ESCALATION",)

        emergency_type = None
        if is_emergency:
            has_environmental = environmental_risk > 0
            has_cross_zone = cross_zone_risk > 0
            has_worker = human_exposure_risk > 0
            if has_environmental and has_cross_zone:
                emergency_type = "ENVIRONMENTAL_HAZARD_WITH_CROSS_ZONE_ESCALATION"
            elif has_environmental:
                emergency_type = "ENVIRONMENTAL_HAZARD"
            elif has_worker:
                emergency_type = "WORKER_SAFETY_EMERGENCY"
            elif permit_conflict_risk > 0:
                emergency_type = "PERMIT_CONFLICT_EMERGENCY"
            else:
                emergency_type = "GENERAL_EMERGENCY"

        incident_context = IncidentContextSummary(
            active_incidents=(),  # not modeled upstream — see module docstring
            emergency_detected=is_emergency,
            emergency_type=emergency_type,
        )
        emergency_decision = EmergencyDecision(is_emergency=is_emergency, triggered_by=triggered_by)

        source_agents: list[str] = []
        evidence_ids: list[str] = []
        seen_agents: set[str] = set()
        seen_evidence: set[str] = set()
        for r in results:
            for item in r.context.evidence.items:
                if item.origin_agent not in seen_agents:
                    seen_agents.add(item.origin_agent)
                    source_agents.append(item.origin_agent)
                if item.evidence_id not in seen_evidence:
                    seen_evidence.add(item.evidence_id)
                    evidence_ids.append(item.evidence_id)
        provenance = Provenance(source_agents=tuple(source_agents), evidence_ids=tuple(evidence_ids))

        risk_reasoning: list[str] = []
        for r in results:
            risk_reasoning.extend(f.description for f in r.findings)
        for entry in interaction_risks:
            risk_reasoning.append(entry.reason)

        return (
            risk_assessment,
            zone_risks,
            interaction_risks,
            permit_risks,
            incident_context,
            risk_breakdown,
            tuple(dict.fromkeys(risk_reasoning)),
            emergency_decision,
            provenance,
        )
