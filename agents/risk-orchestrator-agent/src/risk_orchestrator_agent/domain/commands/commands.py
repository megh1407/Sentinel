"""Command contracts — immutable objects carrying only request
information (the implementation brief's explicit constraint), one per
pipeline stage named in Phase 2.1 §4.2 / Phase 2.4 §3.
"""

from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.domain.validators.base import validate_non_empty_string
from risk_orchestrator_agent.shared.serialization.serializer import Serializable
from risk_orchestrator_agent.shared.utilities.time_utils import new_uuid


@dataclasses.dataclass(frozen=True, slots=True)
class Command(Serializable):
    """Base for every command. Carries a `command_id`/`correlation_id`
    pair so every command can be traced back to the cycle that issued it,
    but no other cross-cutting state — commands are pure request DTOs.
    """

    correlation_id: str
    command_id: str = dataclasses.field(default_factory=new_uuid)


@dataclasses.dataclass(frozen=True, slots=True)
class BuildContextCommand(Command):
    """Request to `ContextBuilder` to merge one domain update and/or
    produce a snapshot (Phase 2.2 §2, §6)."""

    zone_id: str = ""
    domain: str = ""
    payload: dict = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.zone_id, field_name="zone_id")


@dataclasses.dataclass(frozen=True, slots=True)
class EvaluateRiskCommand(Command):
    """Request to run `CorrelationEngine` + `RuleEngine` + `RiskScorer`
    over an already-built `RiskContext` (Phase 2.3 §6/§7, Phase 2.1 §3.5)."""

    zone_id: str = ""
    risk_context_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class PredictRiskCommand(Command):
    """Request to a future/optional prediction engine for a forward-
    looking forecast (Phase 1 §5.3, Phase 2.4 §17)."""

    zone_id: str = ""
    horizon_minutes: int = 20


@dataclasses.dataclass(frozen=True, slots=True)
class GenerateExplanationCommand(Command):
    """Request to `ExplanationBuilder` to assemble an `ExplanationObject`
    (Phase 2.1 §3.9)."""

    zone_id: str = ""
    assessment_id: str = ""
    contributor_ids: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class GenerateRecommendationCommand(Command):
    """Request to `RecommendationCoordinator` to surface/de-duplicate
    upstream recommendations for a decision category (Phase 2.4 §7)."""

    zone_id: str = ""
    decision_category: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class PersistAssessmentCommand(Command):
    """Request to the repository layer to durably persist a finalized
    `RiskAssessment` (Phase 4.2 §5.1's synchronous transaction)."""

    assessment_id: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class PublishAssessmentCommand(Command):
    """Request to `EventPublisher` to publish a finalized `RiskAssessment`
    (Phase 2.1 §3.12)."""

    assessment_id: str = ""
    zone_id: str = ""
