"""memory/adapters/postgres_history_adapter.py — wraps
`sentinel_state.postgres_repositories` (Phase 3.1 §2).

This implementation phase only exercises the read-side of
`HistoryRepositoryPort` (previous severity + recent transitions, feeding
`HistoricalContext`, Phase 2.2 §7). `write_audit_record` is implemented
for interface completeness but is not called by anything in this phase
(AuditManager is a later-phase component, Phase 2.1 §3.11).
"""

from __future__ import annotations

import logging
from datetime import datetime

from risk_orchestrator_agent.domain.models.historical_context import SeverityTransition
from risk_orchestrator_agent.domain.ports.history_repository_port import HistoryRepositoryPort

logger = logging.getLogger(__name__)


class PostgresUnavailableError(Exception):
    """Raised (caught at ContextBuilder's boundary, Phase 2.4 §12) when
    the PostgreSQL client signals unavailability."""


class PostgresHistoryAdapter(HistoryRepositoryPort):
    def __init__(self, pool) -> None:
        """`pool` is an already-constructed async connection pool
        (e.g. `asyncpg.Pool`), injected by `agent.py`'s composition root."""
        self._pool = pool

    async def get_previous_severity(self, zone_id: str) -> tuple[str | None, datetime | None]:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT risk_level, computed_at
                    FROM risk_assessments
                    WHERE zone_id = $1 AND status IN ('current', 'superseded')
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """,
                    zone_id,
                )
        except Exception as exc:  # noqa: BLE001
            raise PostgresUnavailableError(str(exc)) from exc
        if row is None:
            return None, None
        return row["risk_level"], row["computed_at"]

    async def get_recent_transitions(
        self, zone_id: str, *, limit: int = 10
    ) -> tuple[SeverityTransition, ...]:
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT previous_state, new_state, transitioned_at
                    FROM decision_records dr
                    JOIN decisions d ON d.decision_id = dr.decision_id
                    WHERE d.zone_id = $1
                    ORDER BY dr.transitioned_at DESC
                    LIMIT $2
                    """,
                    zone_id,
                    limit,
                )
        except Exception as exc:  # noqa: BLE001
            raise PostgresUnavailableError(str(exc)) from exc
        return tuple(
            SeverityTransition(
                from_severity=r["previous_state"],
                to_severity=r["new_state"],
                transitioned_at=r["transitioned_at"],
            )
            for r in reversed(rows)
        )

    async def write_audit_record(self, record: dict) -> None:
        # Not exercised in this implementation phase (AuditManager is a
        # later-phase component per Phase 2.1 §3.11) — declared for port
        # completeness only.
        raise NotImplementedError("AuditManager is out of scope for this implementation phase")
