"""ContextRepositoryPort (FRS §7). Abstract contract only — no logic, no
state. Implemented by memory/adapters/redis_context_adapter.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from risk_orchestrator_agent.domain.models.risk_context import RiskContext


class ContextRepositoryPort(ABC):
    """Defines *what* rolling per-zone context persistence looks like,
    never *how* (Phase 3.1 §3.4)."""

    @abstractmethod
    async def get(self, zone_id: str) -> RiskContext | None:
        """Read the current rolling RiskContext for `zone_id`, or None if
        this zone has never been seen (Phase 2.2 §5.2's Created state)."""
        raise NotImplementedError

    @abstractmethod
    async def put(self, zone_id: str, context: RiskContext) -> None:
        """Persist the current rolling RiskContext for `zone_id`."""
        raise NotImplementedError

    @abstractmethod
    async def expire(self, zone_id: str) -> None:
        """Explicitly destroy a zone's context (Phase 2.2 §5.8)."""
        raise NotImplementedError
