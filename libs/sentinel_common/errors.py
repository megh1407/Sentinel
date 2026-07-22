"""
errors.py

The platform-wide exception hierarchy. Every SentinelError subclass carries
a correlation_id (auto-populated from the active LoggingContext if not
explicitly passed) and a stable error_code, so every service in SENTINEL
reports failures the same way.
"""
from __future__ import annotations


class SentinelError(Exception):
    """Base for all Sentinel exceptions."""

    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, correlation_id: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if correlation_id is None:
            # Import here (not at module top) to avoid a circular import --
            # logging_context imports nothing from errors, but keeping the
            # dependency one-directional at import time is cleaner.
            from .logging_context import get_correlation_id
            correlation_id = get_correlation_id()
        self.correlation_id = correlation_id

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, correlation_id={self.correlation_id!r})"


class RetryableError(SentinelError):
    """Transient failure -- safe to retry with backoff."""
    error_code = "RETRYABLE_ERROR"


class FatalError(SentinelError):
    """Will never succeed on retry -- routes directly to DLQ."""
    error_code = "FATAL_ERROR"


class ValidationError(FatalError):
    """Input failed schema/contract validation."""
    error_code = "VALIDATION_ERROR"


class ContractViolationError(FatalError):
    """Payload is structurally valid but violates a documented domain invariant."""
    error_code = "CONTRACT_VIOLATION"


class StateError(RetryableError):
    """A state store (Postgres/Redis/Neo4j/Vector) operation failed."""
    error_code = "STATE_ERROR"


class ConfigurationError(FatalError):
    """Config failed validation at load time."""
    error_code = "CONFIGURATION_ERROR"


class SecurityError(FatalError):
    """AuthN/AuthZ failure. Never retried, always audited."""
    error_code = "SECURITY_ERROR"
