"""Root exception hierarchy for the Risk Orchestrator domain layer.

Mirrors the platform-wide exception hierarchy established in the Coding
Standards specification (CSEGS §6.1):

    SentinelException (base)
    +-- ValidationException
    +-- DomainException
    +-- EventContractException
    +-- ContextBuildException
    +-- CorrelationException
    +-- RuleEvaluationException
    +-- PredictionException
    +-- RecommendationException
    +-- PersistenceException

Every exception carries structured context (`error_code`, `severity`,
`retryable`, `metadata`, `correlation_id`, `timestamp`) rather than a bare
string message, consistent with CSEGS §6.2's rule against unstructured
business exceptions.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Mapping

from risk_orchestrator_agent.shared.typing.types import Metadata
from risk_orchestrator_agent.shared.utilities.time_utils import utc_now


class ExceptionSeverity(str, Enum):
    """How serious this exception is, independent of whether it's retryable."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SentinelException(Exception):
    """Base class for every exception raised anywhere in this domain layer.

    Never raised directly — always via one of the typed subclasses below,
    consistent with CSEGS §6.1's "never raise a bare Exception" rule.
    """

    #: A short, stable, machine-matchable identifier for this failure kind.
    #: Subclasses override this; the base default exists only so the
    #: field is never unset.
    error_code: str = "SENTINEL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        severity: ExceptionSeverity = ExceptionSeverity.ERROR,
        retryable: bool = False,
        metadata: Metadata | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.error_code
        self.severity = severity
        self.retryable = retryable
        self.metadata: Mapping[str, Any] = dict(metadata or {})
        self.correlation_id = correlation_id
        self.timestamp = utc_now()

    def to_dict(self) -> dict[str, Any]:
        """Structured representation suitable for logging (CSEGS §7.1)."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "metadata": dict(self.metadata),
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{type(self).__name__}(error_code={self.error_code!r}, message={self.message!r})"


class ValidationException(SentinelException):
    """Raised when input fails validation at a domain boundary.

    Always the caller's fault (CSEGS §6.1) — never retryable by default,
    since retrying identical invalid input produces the identical failure.
    """

    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        super().__init__(message, **kwargs)


class DomainException(SentinelException):
    """Raised when a domain invariant is violated (Phase 2.5 §9)."""

    error_code = "DOMAIN_INVARIANT_VIOLATION"


class EventContractException(SentinelException):
    """Raised when an event fails schema/envelope validation (Phase 1 §4.8)."""

    error_code = "EVENT_CONTRACT_VIOLATION"


class ContextBuildException(DomainException):
    """Raised for a `ContextBuilder`-stage structural failure (Phase 2.2 §6)."""

    error_code = "CONTEXT_BUILD_ERROR"


class CorrelationException(DomainException):
    """Raised for a `CorrelationEngine`-stage structural failure (Phase 2.3 §2)."""

    error_code = "CORRELATION_ERROR"


class RuleEvaluationException(DomainException):
    """Raised for a `RuleEngine`-stage evaluation failure (Phase 2.3 §3)."""

    error_code = "RULE_EVALUATION_ERROR"


class PredictionException(DomainException):
    """Raised for a prediction-engine-stage failure (Phase 1 §5.3)."""

    error_code = "PREDICTION_ERROR"


class RecommendationException(DomainException):
    """Raised for a `RecommendationCoordinator`-stage failure (Phase 2.1 §3.9).

    Per Phase 2.1 §3.8's contract, this component "cannot fail the
    scoring cycle" — this exception type exists for completeness of the
    hierarchy and for defensive programming at call sites, not because
    the architecture expects it to be raised in the steady state.
    """

    error_code = "RECOMMENDATION_ERROR"


class PersistenceException(SentinelException):
    """Raised for a repository/adapter-level persistence failure."""

    error_code = "PERSISTENCE_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", True)
        super().__init__(message, **kwargs)


@dataclasses.dataclass(frozen=True)
class ExceptionContext:
    """Structured context object for constructing an exception's metadata.

    Optional convenience — call sites may pass a plain dict to `metadata`
    directly, or build one of these first for readability when several
    fields are involved.
    """

    zone_id: str | None = None
    site_id: str | None = None
    event_id: str | None = None
    rule_id: str | None = None
    finding_id: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}
