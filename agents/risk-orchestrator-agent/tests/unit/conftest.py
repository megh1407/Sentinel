"""tests/unit/conftest.py — shared fixtures.

`FakeAsyncRedis` is a minimal in-memory stand-in supporting exactly the
Redis commands `RedisContextAdapter` uses (get/set/delete/pipeline/
incr/expire/rpush/ltrim/lrange), so adapter and pipeline tests never
require a real Redis instance (per this phase's "Use mocked Kafka and
repositories" testing requirement).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest


class _FakePipeline:
    def __init__(self, client: "FakeAsyncRedis") -> None:
        self._client = client
        self._ops: list[tuple[str, tuple]] = []

    def incr(self, key: str) -> "_FakePipeline":
        self._ops.append(("incr", (key,)))
        return self

    def set(self, key: str, value: str, ex: int | None = None) -> "_FakePipeline":
        self._ops.append(("set", (key, value, ex)))
        return self

    def expire(self, key: str, seconds: int) -> "_FakePipeline":
        self._ops.append(("expire", (key, seconds)))
        return self

    def rpush(self, key: str, value: str) -> "_FakePipeline":
        self._ops.append(("rpush", (key, value)))
        return self

    def ltrim(self, key: str, start: int, end: int) -> "_FakePipeline":
        self._ops.append(("ltrim", (key, start, end)))
        return self

    async def execute(self) -> list[Any]:
        results = []
        for op, args in self._ops:
            results.append(await getattr(self._client, f"_{op}")(*args))
        self._ops.clear()
        return results

    async def __aenter__(self) -> "_FakePipeline":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.fail: bool = False

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self)

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise ConnectionError("simulated redis outage")
        return self.store.get(key)

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
            if k in self.lists:
                del self.lists[k]
        return count

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def _incr(self, key: str) -> int:
        current = int(self.store.get(key, "0")) + 1
        self.store[key] = str(current)
        return current

    async def _set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def _expire(self, key: str, seconds: int) -> None:
        pass

    async def _rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    async def _ltrim(self, key: str, start: int, end: int) -> None:
        values = self.lists.get(key, [])
        if end == -1:
            self.lists[key] = values[start:]
        else:
            self.lists[key] = values[start : end + 1]


@pytest.fixture
def fake_redis() -> FakeAsyncRedis:
    return FakeAsyncRedis()


def make_agent_result(
    *,
    result_type: str,
    zone_id: str = "zone-17",
    site_id: str = "site-04",
    payload: dict,
    event_id: str = "evt-1",
    correlation_id: str = "corr-1",
    confidence: float = 0.9,
    agent_id: str | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": f"{result_type}.complete",
        "event_version": 1,
        "timestamp": datetime(2026, 7, 5, 9, 12, 0, tzinfo=timezone.utc).isoformat(),
        "source": agent_id or f"{result_type}_agent",
        "site_id": site_id,
        "zone_id": zone_id,
        "correlation_id": correlation_id,
        "causation_id": None,
        "schema_version": "v1",
        "agent_id": agent_id or f"{result_type}_agent",
        "agent_version": "1.0.0",
        "input_events": [],
        "result_type": result_type,
        "confidence": confidence,
        "processing_time_ms": 100,
        "error": None,
        "payload": {"analyzed_at": datetime(2026, 7, 5, 9, 12, 0, tzinfo=timezone.utc).isoformat(), **payload},
    }
