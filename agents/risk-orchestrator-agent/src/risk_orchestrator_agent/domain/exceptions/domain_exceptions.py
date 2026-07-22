"""Specific, named exceptions referenced by the architecture documents.

Includes the Infrastructure/Retryable/Fatal split from CSEGS §6.1 and the
three concrete exception types FRS §4.6 names as "the only exceptions
permitted to cross a domain-service boundary": `ContextValidationError`,
`IncompleteExplanationError`, and `RuleSetLoadError`.
"""

from __future__ import annotations

from typing import Any

from risk_orchestrator_agent.domain.exceptions.base import (
    ContextBuildException,
    DomainException,
    ExceptionSeverity,
    PersistenceException,
    SentinelException,
)


class InfrastructureError(SentinelException):
    """A Kafka/DB/Neo4j/Qdrant/Redis failure (CSEGS §6.1)."""

    error_code = "INFRASTRUCTURE_ERROR"


class RetryableError(InfrastructureError):
    """A transient infrastructure failure — safe to retry (CSEGS §6.1)."""

    error_code = "RETRYABLE_INFRASTRUCTURE_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", True)
        super().__init__(message, **kwargs)


class FatalError(InfrastructureError):
    """A non-transient infrastructure failure — must not be retried blindly
    (CSEGS §6.1)."""

    error_code = "FATAL_INFRASTRUCTURE_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("severity", ExceptionSeverity.CRITICAL)
        super().__init__(message, **kwargs)


class ContextValidationError(ContextBuildException):
    """Raised by `ContextBuilder`'s validation step when an assembled
    `RiskContext` fails structural validation (Phase 2.2 §6.1, FRS §4.6).

    Routed to DLQ by `application/scoring_pipeline.py` — never allowed to
    silently propagate a corrupted context downstream (Phase 2.1 §9.4).
    """

    error_code = "CONTEXT_VALIDATION_ERROR"


class IncompleteExplanationError(DomainException):
    """Raised by `ExplanationBuilder` when a non-negligible score would
    otherwise ship without a complete evidence chain (Phase 1 §9.4,
    Phase 2.1 §9.4, FRS §4.6).

    This is the one domain exception explicitly permitted, by design, to
    hard-fail an entire scoring cycle (FRS §3.7's "Error Handling" row).
    """

    error_code = "INCOMPLETE_EXPLANATION_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("severity", ExceptionSeverity.CRITICAL)
        kwargs.setdefault("retryable", False)
        super().__init__(message, **kwargs)


class RuleSetLoadError(PersistenceException):
    """Raised by `config/rule_config_loader.py` when a rule-set payload
    fails validation at load time (Phase 2.3 §12.2's fail-closed rule,
    FRS §4.6).

    Caught by `agent.py`'s `lifecycle.py`, halting startup (if raised
    during initial load) or rejecting a hot-reload while retaining the
    previously-valid rule set (if raised during a reload).
    """

    error_code = "RULE_SET_LOAD_ERROR"

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("severity", ExceptionSeverity.CRITICAL)
        super().__init__(message, **kwargs)


class ConfigurationValidationError(FatalError):
    """Raised when a configuration snapshot fails schema/cross-consistency
    validation (Phase 2.1 §3.13, ALDS §10.3). Fail-closed: the process
    never reaches `READY` with an unvalidated configuration.
    """

    error_code = "CONFIGURATION_VALIDATION_ERROR"


class EvidenceChainBrokenError(DomainException):
    """Raised when a contributor entering `DecisionEngine` carries a
    broken evidence chain (Phase 2.4 §2's Evidence Validation
    responsibility). The offending contributor is excluded and logged,
    never silently trusted.
    """

    error_code = "EVIDENCE_CHAIN_BROKEN"


class CircularRuleDependencyError(RuleSetLoadError):
    """Raised at rule-set load time when rule chaining declarations form
    a cycle (Phase 2.3 §7.3's prohibition on circular rule dependencies).
    """

    error_code = "CIRCULAR_RULE_DEPENDENCY"
