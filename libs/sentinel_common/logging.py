"""
logging.py

Structured JSON logging built on structlog. Every log line automatically
carries correlation_id/causation_id/audit_id from the active LoggingContext
-- callers never pass these manually. A PII-redaction processor runs before
every line is emitted, using a static, code-reviewed field-name list (not
runtime-configurable, so it can't be silently disabled by a bad config).
"""
from __future__ import annotations

import logging
import sys

import structlog

from .logging_context import get_audit_id, get_causation_id, get_correlation_id

# Static, code-reviewed. NOT loaded from config -- see module docstring.
_REDACTED_FIELD_NAMES = {
    "name", "full_name", "email", "phone", "ssn", "badge_photo",
    "address", "date_of_birth", "national_id",
}
_REDACTED_PLACEHOLDER = "***REDACTED***"


def _inject_correlation_ids(logger, method_name, event_dict):
    event_dict["correlation_id"] = get_correlation_id()
    event_dict["causation_id"] = get_causation_id()
    event_dict["audit_id"] = get_audit_id()
    return event_dict


def _redact_pii(logger, method_name, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _REDACTED_FIELD_NAMES:
            event_dict[key] = _REDACTED_PLACEHOLDER
    return event_dict


_configured = False


def configure_logging(service_name: str, level: int = logging.INFO) -> None:
    """One-time bootstrap. Call once per process (AgentRunner.initialize() does
    this automatically). Safe to call more than once -- subsequent calls are
    no-ops."""
    global _configured
    if _configured:
        return

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _inject_correlation_ids,
            _redact_pii,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.BoundLogger:
    """Returns a logger pre-bound with `service`/`logger` context. Configures
    logging with sensible defaults on first call if configure_logging() was
    never explicitly invoked (e.g. in a quick script or a test)."""
    if not _configured:
        configure_logging(service_name=name)
    return structlog.get_logger(name).bind(logger=name)
