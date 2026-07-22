"""Response DTOs — immutable internal responses (never API responses,
per the implementation brief) returned by each pipeline stage's engine
interface (`domain/interfaces/engines.py`).
"""

from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.shared.serialization.serializer import Serializable


@dataclasses.dataclass(frozen=True, slots=True)
class Response(Serializable):
    """Base for every internal response. `success`/`error_message` give
    every response a uniform way to report a non-exceptional failure
    (e.g., a degraded-but-not-fatal outcome, Phase 2.1 §10.2) without
    every caller needing a try/except for the common case.
    """

    success: bool = True
    error_message: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class ContextBuildResult(Response):
    """Result of a `ContextBuilder` operation (Phase 2.2 §6)."""

    zone_id: str = ""
    risk_context_id: str = ""
    completeness: float = 1.0
    missing_domains: tuple[str, ...] = ()
    degraded: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class CorrelationResult(Response):
    """Result of a `CorrelationEngine` operation (Phase 2.3 §2/§6)."""

    zone_id: str = ""
    finding_ids: tuple[str, ...] = ()
    topology_unavailable: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class PredictionResult(Response):
    """Result of a prediction-engine operation (Phase 1 §5.3)."""

    zone_id: str = ""
    predicted_probability: float | None = None
    horizon_minutes: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class RiskScoreResult(Response):
    """Result of a `RiskScorer` operation (Phase 2.1 §3.5)."""

    zone_id: str = ""
    score: int = 0
    contributor_ids: tuple[str, ...] = ()
    partial_weighting: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class DecisionResult(Response):
    """Result of a `DecisionEngine` operation (Phase 2.4 §2/§3)."""

    zone_id: str = ""
    decision_category: str = ""
    severity: str = "negligible"
    ttl_seconds: int = 30
    risk_level_changed: bool = False
    manual_review_required: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class ExplanationResult(Response):
    """Result of an `ExplanationBuilder` operation (Phase 2.1 §3.9)."""

    assessment_id: str = ""
    explanation_id: str = ""
    complete: bool = True


@dataclasses.dataclass(frozen=True, slots=True)
class RecommendationResult(Response):
    """Result of a `RecommendationCoordinator` operation (Phase 2.1 §3.9)."""

    zone_id: str = ""
    signal_ids: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class RepositoryResult(Response):
    """Generic result of a repository read/write operation (Phase 2.1
    §3.10) — used where a typed domain-object return isn't itself the
    whole answer (e.g., a write acknowledgement)."""

    affected_id: str = ""
    degraded: bool = False
