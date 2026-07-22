"""services/context_replay_service.py.

An additive `services/*` file (FRS §14.1's "New Service" extension
pattern: "a new services/* file, constructed at the existing 'Create
Application Services' step... contains no pure business logic"),
realizing this implementation phase's Event Timeline & Replay Manager
requirement: replay support and time-travel reconstruction over the
bounded snapshot-history ring buffer (`RedisContextAdapter.
append_snapshot_history`/`get_snapshot_history`).

Coordinates domain + ports but is not itself pure domain logic — it
never computes risk, never mutates `RiskContext`, and depends only on
`domain/models/*` and the already-injected adapter, consistent with
Phase 3.1 §4's `services/` layer rule.
"""

from __future__ import annotations

from datetime import datetime

from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter


class ContextReplayService:
    def __init__(self, redis_context_adapter: RedisContextAdapter) -> None:
        self._adapter = redis_context_adapter

    async def record(self, zone_id: str, context: RiskContext) -> None:
        """Append one snapshot to the zone's replay history. Called by
        the pipeline immediately after `ContextBuilder.snapshot()`."""
        await self._adapter.append_snapshot_history(zone_id, context)

    async def history(self, zone_id: str, *, limit: int = 50) -> tuple[RiskContext, ...]:
        """Ordered oldest-to-newest snapshot history, for debugging and
        replay tooling."""
        return await self._adapter.get_snapshot_history(zone_id, limit=limit)

    async def reconstruct_at(self, zone_id: str, *, at_or_before: datetime) -> RiskContext | None:
        """Time-travel reconstruction: the most recent snapshot whose
        `snapshot_at` is at or before the requested instant."""
        history = await self.history(zone_id, limit=500)
        candidates = [ctx for ctx in history if ctx.snapshot_at <= at_or_before]
        return candidates[-1] if candidates else None

    async def current_version(self, zone_id: str) -> int:
        return await self._adapter.get_version(zone_id)
