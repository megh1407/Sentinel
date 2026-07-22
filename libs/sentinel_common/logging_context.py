"""
logging_context.py

Real contextvars-based propagation of correlation_id / causation_id /
audit_id. Set once per unit of work (by AgentRunner, per event processed);
read anywhere downstream (loggers, error classes, tracers) without having to
thread the IDs through every function signature by hand.
"""
from __future__ import annotations

import contextvars

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)
_causation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("causation_id", default=None)
_audit_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("audit_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_causation_id() -> str | None:
    return _causation_id.get()


def get_audit_id() -> str | None:
    return _audit_id.get()


class LoggingContext:
    """Context manager that binds correlation/causation/audit IDs for the
    duration of processing one event. AgentRunner opens one of these per
    consumed event; business logic never sets these manually."""

    def __init__(self, correlation_id: str, causation_id: str | None = None, audit_id: str | None = None):
        self.correlation_id = correlation_id
        self.causation_id = causation_id
        self.audit_id = audit_id
        self._tokens: list[tuple[contextvars.ContextVar, contextvars.Token]] = []

    def __enter__(self) -> "LoggingContext":
        self._tokens.append((_correlation_id, _correlation_id.set(self.correlation_id)))
        self._tokens.append((_causation_id, _causation_id.set(self.causation_id)))
        self._tokens.append((_audit_id, _audit_id.set(self.audit_id)))
        return self

    def __exit__(self, *exc) -> None:
        for var, token in reversed(self._tokens):
            var.reset(token)
        self._tokens.clear()
