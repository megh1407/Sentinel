"""`RiskAssessment` aggregate root and its contained entities/collections
(Phase 2.5 §3.2, §5; Phase 1 §5.1; Phase 2.4).

`CompoundRisk` and `RecommendationSet` are modeled here as thin entities
wrapping what Phase 2.5 §3's cover note establishes are really Value
Object subtypes / contained collections — kept as named classes because
the implementation brief calls them out explicitly, but they carry no
independent repository or lifecycle (Phase 2.5 §3.5, §11.1).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from risk_orchestrator_agent.domain.entities.base import Entity
from risk_orchestrator_agent.domain.enums.risk import (
    DecisionCategory,
    RecommendationCategory,
    RecommendationPriority,
    RiskCategory,
    RiskLevel,
)
from risk_orchestrator_agent.domain.enums.status import RiskAssessmentStatus
from risk_orchestrator_agent.domain.value_objects.evidence import EvidenceReference, RiskReason
from risk_orchestrator_agent.shared.utilities.time_utils import utc_now


@dataclasses.dataclass(eq=False)
class RiskContributor(Entity):
    """One named, evidenced contributor to a `RiskAssessment`'s score
    (Phase 1 §5.1's `contributors[]`)."""

    agent: str = ""
    factor: str = ""
    category: RiskCategory = RiskCategory.DIRECT
    weight: float = 0.0
    score: int = 0
    evidence: tuple[EvidenceReference, ...] = ()


@dataclasses.dataclass(eq=False)
class CompoundRisk(Entity):
    """A specially-flagged compound finding (Phase 2.3 §5, Phase 2.5 §3
    cover note #1 — not an independent aggregate root, contained within
    a `RiskAssessment`).
    """

    factor_name: str = ""
    business_meaning: str = ""
    contributing_agent_ids: tuple[str, ...] = ()
    contributing_finding_ids: tuple[str, ...] = ()
    severity_contribution: RiskLevel = RiskLevel.MODERATE
    confidence: float = 0.0
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        from risk_orchestrator_agent.domain.constants.limits import (
            MIN_DISTINCT_AGENTS_FOR_COMPOUND_FINDING,
        )
        from risk_orchestrator_agent.domain.exceptions.base import DomainException

        if len(set(self.contributing_agent_ids)) < MIN_DISTINCT_AGENTS_FOR_COMPOUND_FINDING:
            raise DomainException(
                "A CompoundRisk requires evidence from at least "
                f"{MIN_DISTINCT_AGENTS_FOR_COMPOUND_FINDING} distinct upstream agents "
                f"(Phase 2.3 §5.5); got {self.contributing_agent_ids!r}"
            )


@dataclasses.dataclass(eq=False)
class EmergencyAssessment(Entity):
    """The urgency-signal metadata attached when a `RiskAssessment`
    reaches the Emergency classification tier (Phase 2.4 §6.1).

    A classification/signal record only — it never represents an
    executed action (Phase 2.4 §1.4's terminology reconciliation).
    """

    zone_id: str = ""
    severity: RiskLevel = RiskLevel.CRITICAL
    ttl_seconds: int = 15
    delivery_tier: str = "acks_all"
    triggered_at: datetime = dataclasses.field(default_factory=utc_now)


@dataclasses.dataclass(eq=False)
class DecisionExplanation(Entity):
    """Realizes `ExplanationObject` (Phase 2.1 §3.9, Phase 2.5 §5) as an
    entity for identity/versioning convenience, even though its
    *contents* are treated as immutable once attached to a
    `RiskAssessment` (Phase 2.4 §16.1).
    """

    summary: str = ""
    reasoning_steps: tuple[RiskReason, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    risk_contributors: tuple[str, ...] = ()  # RiskContributor entity_ids
    alternatives_considered: tuple[str, ...] = ()


@dataclasses.dataclass(eq=False)
class Recommendation(Entity):
    """One surfaced, category-tagged, verbatim-upstream recommendation
    signal (`RecommendationSignal`, Phase 2.5 §5)."""

    category: RecommendationCategory = RecommendationCategory.PPE_RECOMMENDATION
    text: str = ""
    source_input_analysis_id: str = ""
    priority: RecommendationPriority = RecommendationPriority.P3_STANDARD


@dataclasses.dataclass(eq=False)
class RecommendationSet(Entity):
    """The immutable, de-duplicated collection of `Recommendation`s
    attached to one `RiskAssessment` (Phase 2.5 §3's reconciliation #3 —
    not an independent aggregate root)."""

    assessment_id: str = ""
    signals: tuple[Recommendation, ...] = ()

    def is_empty(self) -> bool:
        return len(self.signals) == 0


@dataclasses.dataclass(eq=False)
class RiskAssessment(Entity):
    """Realizes `RiskScore` (Phase 1 §5.1) as this bounded context's own
    internal aggregate root name (Phase 2.5 §3.2) — the complete,
    immutable outcome of exactly one scoring cycle for one zone.

    Business invariant (Phase 2.5 §9): must contain at least one
    `RiskContributor`; enforced in `__post_init__` below.
    """

    zone_id: str = ""
    site_id: str = ""
    score: int = 0
    severity: RiskLevel = RiskLevel.NEGLIGIBLE
    decision_category: DecisionCategory = DecisionCategory.SAFE
    contributors: tuple[RiskContributor, ...] = ()
    compound_risks: tuple[CompoundRisk, ...] = ()
    explanation: DecisionExplanation | None = None
    recommendation_set: RecommendationSet | None = None
    emergency_assessment: EmergencyAssessment | None = None
    computed_at: datetime = dataclasses.field(default_factory=utc_now)
    ttl_seconds: int = 30
    risk_level_changed: bool = False
    status: RiskAssessmentStatus = RiskAssessmentStatus.CREATED
    input_analysis_ids: tuple[str, ...] = ()
    context_builder_version: str = "1.0.0"
    rule_set_version: str = "1.0.0"
    confidence: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        from risk_orchestrator_agent.domain.exceptions.base import DomainException

        if len(self.contributors) == 0:
            raise DomainException(
                "A RiskAssessment must contain at least one RiskContributor "
                "(Phase 2.5 §9) — an assessment with zero findings represents "
                "'nothing was computed', not 'the situation is safe'."
            )


@dataclasses.dataclass(eq=False)
class HistoricalRisk(Entity):
    """A durable, previously-published `RiskAssessment` outcome retained
    for trend/history queries (Phase 2.2 §3, `HistoricalContext` source)."""

    zone_id: str = ""
    assessment_id: str = ""
    severity: RiskLevel = RiskLevel.NEGLIGIBLE
    score: int = 0
    computed_at: datetime = dataclasses.field(default_factory=utc_now)


@dataclasses.dataclass(eq=False)
class LiveRiskSnapshot(Entity):
    """The current, Redis-backed rolling view of a zone's most recent
    `RiskAssessment` outcome — distinct from `HistoricalRisk`'s durable
    PostgreSQL-backed record (Phase 2.2 §13.3's cache-first read pattern).
    """

    zone_id: str = ""
    assessment_id: str = ""
    severity: RiskLevel = RiskLevel.NEGLIGIBLE
    score: int = 0
    expires_at: datetime | None = None
