from __future__ import annotations

from risk_orchestrator_agent.domain.context.context_builder import _empty_context
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter
from risk_orchestrator_agent.services.context_replay_service import ContextReplayService


async def test_put_then_get_round_trips_exactly(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    context = _empty_context("zone-17", "site-04")

    await adapter.put("zone-17", context)
    restored = await adapter.get("zone-17")

    assert restored is not None
    assert restored.zone_id == context.zone_id
    assert restored.site_id == context.site_id
    assert restored.quality.completeness == context.quality.completeness


async def test_get_on_never_written_zone_returns_none(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    assert await adapter.get("zone-never-written") is None


async def test_version_increments_on_every_put(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    context = _empty_context("zone-17", "site-04")

    assert await adapter.get_version("zone-17") == 0
    await adapter.put("zone-17", context)
    assert await adapter.get_version("zone-17") == 1
    await adapter.put("zone-17", context)
    assert await adapter.get_version("zone-17") == 2


async def test_expire_removes_context_and_version(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    context = _empty_context("zone-17", "site-04")
    await adapter.put("zone-17", context)

    await adapter.expire("zone-17")

    assert await adapter.get("zone-17") is None
    assert await adapter.get_version("zone-17") == 0


async def test_snapshot_history_is_ordered_oldest_to_newest(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    replay = ContextReplayService(adapter)

    for i in range(3):
        ctx = _empty_context("zone-17", "site-04")
        await replay.record("zone-17", ctx)

    history = await replay.history("zone-17", limit=10)
    assert len(history) == 3


async def test_reconstruct_at_returns_most_recent_snapshot_at_or_before(fake_redis) -> None:
    import dataclasses
    from datetime import datetime, timedelta, timezone

    adapter = RedisContextAdapter(fake_redis)
    replay = ContextReplayService(adapter)

    base = _empty_context("zone-17", "site-04")
    t0 = datetime(2026, 7, 5, 9, 0, 0, tzinfo=timezone.utc)
    ctx1 = dataclasses.replace(base, snapshot_at=t0)
    ctx2 = dataclasses.replace(base, snapshot_at=t0 + timedelta(minutes=5))

    await replay.record("zone-17", ctx1)
    await replay.record("zone-17", ctx2)

    reconstructed = await replay.reconstruct_at("zone-17", at_or_before=t0 + timedelta(minutes=1))
    assert reconstructed is not None
    assert reconstructed.snapshot_at == t0
