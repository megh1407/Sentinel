"""memory/adapters/redis_context_adapter.py — wraps `sentinel_state`'s
Redis-backed rolling context store (Phase 3.1 §2).

Implements `ContextRepositoryPort`. The *only* place a Redis client
import is permitted (Phase 3.1 §3.2). Key structure and TTL policy
follow the Redis Integration Design specification: `sentinel:v1:zone:
{zone_id}` (Section 3), 10-minute Zone Context TTL refreshed on write
(Section 4), and a monotonic per-key version counter satisfying this
phase's context-versioning requirement.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from risk_orchestrator_agent.domain.models.risk_context import RiskContext
from risk_orchestrator_agent.domain.ports.context_repository_port import ContextRepositoryPort
from risk_orchestrator_agent.memory.adapters import _risk_context_codec as codec

logger = logging.getLogger(__name__)

KEY_PREFIX = "sentinel:v1:zone"
DEFAULT_TTL = timedelta(minutes=10)  # Zone Context TTL (Redis design §4.1)


class RedisUnavailableError(Exception):
    """Raised (never to the domain layer — caught at ContextBuilder's
    boundary, Phase 2.2 §5.7) when the Redis client itself signals
    unavailability."""


class RedisContextAdapter(ContextRepositoryPort):
    def __init__(self, client, *, ttl: timedelta = DEFAULT_TTL) -> None:
        """`client` is an already-constructed async Redis client
        (`redis.asyncio.Redis`), injected by `agent.py`'s composition
        root — this adapter never constructs its own connection pool
        (Phase 3.1 §3.4)."""
        self._client = client
        self._ttl = ttl

    @staticmethod
    def _key(zone_id: str) -> str:
        return f"{KEY_PREFIX}:{zone_id}"

    @staticmethod
    def _version_key(zone_id: str) -> str:
        return f"{KEY_PREFIX}:{zone_id}:version"

    async def get(self, zone_id: str) -> RiskContext | None:
        try:
            raw = await self._client.get(self._key(zone_id))
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc
        if raw is None:
            return None
        data = json.loads(raw)
        return codec.decode(data)

    async def put(self, zone_id: str, context: RiskContext) -> None:
        payload = codec.encode(context)
        try:
            # Atomic update: pipeline the version increment and the
            # content write together (Redis design §5.1's "Cache update"
            # is a partial-field update in principle; here the whole
            # RiskContext is written as one unit since it's already
            # composed as a single logical aggregate).
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.incr(self._version_key(zone_id))
                pipe.set(self._key(zone_id), json.dumps(payload), ex=int(self._ttl.total_seconds()))
                pipe.expire(self._version_key(zone_id), int(self._ttl.total_seconds()))
                await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc

    async def expire(self, zone_id: str) -> None:
        try:
            await self._client.delete(self._key(zone_id), self._version_key(zone_id))
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc

    async def get_version(self, zone_id: str) -> int:
        try:
            raw = await self._client.get(self._version_key(zone_id))
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc
        return int(raw) if raw is not None else 0

    # -- Snapshot history / replay (additive to the port's core contract;
    # backs services/context_replay_service.py's "Event Timeline & Replay"
    # requirement) --------------------------------------------------

    @staticmethod
    def _history_key(zone_id: str) -> str:
        return f"{KEY_PREFIX}:{zone_id}:history"

    async def append_snapshot_history(
        self, zone_id: str, context: RiskContext, *, max_entries: int = 500
    ) -> None:
        """Bounded, append-only ring buffer of past snapshots (most
        recent last) supporting replay/time-travel reconstruction. This
        is deliberately separate from `OperationalTimeline` (a fast,
        bounded-window trend projection, Phase 2.2 §9.2) — this history
        is full-snapshot-fidelity, capped by entry count rather than
        time, and exists purely for debugging/replay (per this phase's
        brief), not for correlation input."""
        payload = codec.encode(context)
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.rpush(self._history_key(zone_id), json.dumps(payload))
                pipe.ltrim(self._history_key(zone_id), -max_entries, -1)
                pipe.expire(self._history_key(zone_id), int(self._ttl.total_seconds()) * 6)
                await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc

    async def get_snapshot_history(
        self, zone_id: str, *, limit: int = 50
    ) -> tuple[RiskContext, ...]:
        try:
            raw_entries = await self._client.lrange(self._history_key(zone_id), -limit, -1)
        except Exception as exc:  # noqa: BLE001
            raise RedisUnavailableError(str(exc)) from exc
        return tuple(codec.decode(json.loads(raw)) for raw in raw_entries)
