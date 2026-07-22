"""HistoryRepositoryPort (FRS §7). Abstract contract only.
Implemented by memory/adapters/postgres_history_adapter.py.

This implementation phase uses only the read-side (`get_previous_severity`,
`get_recent_transitions`) to populate `HistoricalContext` (Phase 2.2 §7).
The audit-write side (`write_audit_record`) is declared here for
hierarchy completeness per FRS §7 but is not exercised until AuditManager
is implemented in a later phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from risk_orchestrator_agent.domain.models.historical_context import SeverityTransition


class HistoryRepositoryPort(ABC):
    @abstractmethod
    async def get_previous_severity(self, zone_id: str) -> tuple[str | None, datetime | None]:
        """Returns (previous_severity, previous_computed_at), or (None, None)
        if no prior scoring cycle exists for this zone."""
        raise NotImplementedError

    @abstractmethod
    async def get_recent_transitions(
        self, zone_id: str, *, limit: int = 10
    ) -> tuple[SeverityTransition, ...]:
        """Returns the zone's recent severity trajectory (Phase 2.2 §7),
        most-recent-last."""
        raise NotImplementedError

    @abstractmethod
    async def write_audit_record(self, record: dict) -> None:
        """Not exercised in this implementation phase — declared for
        interface completeness (Phase 2.1 §3.11 is a later-phase
        component)."""
        raise NotImplementedError
