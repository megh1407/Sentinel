"""Domain-layer exceptions for the Risk Orchestrator.

Per FRS §4.6, these are the ONLY exception types permitted to cross a
domain-service boundary. Every other failure mode documented in the
architecture series (missing domain, stale data, low confidence, contested
finding) is modeled as a *flagged value*, never an exception — consistent
with the platform-wide rule that absence of information is never
represented as an error condition (Phase 2.2 §12.3).

This module lives at `domain/exceptions.py`, additive to Phase 3.1's
original tree per FRS §4.6's own justification.
"""

from __future__ import annotations


class SentinelDomainError(Exception):
    """Base class for all Risk Orchestrator domain-layer exceptions."""


class ContextValidationError(SentinelDomainError):
    """Raised by ContextBuilder's validation step (Phase 2.2 §6.1) when an
    assembled RiskContext fails structural validation and must not be
    handed downstream. Caught by application/scoring_pipeline.py and
    routed to DLQ (Phase 2.1 §9.4)."""

    def __init__(self, message: str, *, zone_id: str | None = None, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.zone_id = zone_id
        self.reasons = reasons or []


class IncompleteExplanationError(SentinelDomainError):
    """Raised by explanation_builder.py per Phase 2.1 §9.4's hard-fail rule.
    Not raised during this implementation phase (explanation generation is
    out of scope), but declared here per FRS §4.6 so the exception
    hierarchy is complete and stable for Phase 5."""


class RuleSetLoadError(SentinelDomainError):
    """Raised by config/rule_config_loader.py per Phase 2.3 §12.2's
    fail-closed rule. Not exercised during this implementation phase
    (rule evaluation is out of scope), declared here for hierarchy
    completeness per FRS §4.6."""
