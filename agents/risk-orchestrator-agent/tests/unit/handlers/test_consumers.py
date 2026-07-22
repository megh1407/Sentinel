from __future__ import annotations

import pytest

from risk_orchestrator_agent.handlers.consumers import EventRouter
from tests.unit.conftest import make_agent_result


class _CollectingSink:
    def __init__(self) -> None:
        self.routed: list[tuple[str, dict, str]] = []

    async def route(self, topic: str, raw: dict, reason: str) -> None:
        self.routed.append((topic, raw, reason))


async def test_valid_event_is_dispatched_to_handler() -> None:
    handled = []

    async def handler(dto):
        handled.append(dto)

    router = EventRouter(handler)
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    await router.route("sentinel.worker.analysis.v1", raw)

    assert len(handled) == 1
    assert handled[0].zone_id == "zone-17"
    assert router.metrics.messages_consumed_total == 1


async def test_unrecognized_topic_routes_to_dlq() -> None:
    async def handler(dto):
        pass

    sink = _CollectingSink()
    router = EventRouter(handler, dead_letter_sink=sink)
    await router.route("sentinel.unknown.topic.v1", {"event_id": "x"})

    assert len(sink.routed) == 1
    assert router.metrics.dlq_routed_total == 1


async def test_malformed_event_routes_to_dlq_not_raised() -> None:
    async def handler(dto):
        pass

    sink = _CollectingSink()
    router = EventRouter(handler, dead_letter_sink=sink)
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    del raw["confidence"]

    await router.route("sentinel.worker.analysis.v1", raw)  # must not raise

    assert len(sink.routed) == 1
    assert sink.routed[0][2].startswith("Missing required fields") or "Missing" in sink.routed[0][2]


async def test_duplicate_event_id_is_skipped_not_double_dispatched() -> None:
    handled = []

    async def handler(dto):
        handled.append(dto)

    router = EventRouter(handler)
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"}, event_id="dupe-1")

    await router.route("sentinel.worker.analysis.v1", raw)
    await router.route("sentinel.worker.analysis.v1", dict(raw))  # redelivery

    assert len(handled) == 1
    assert router.metrics.duplicates_skipped_total == 1


async def test_different_zones_do_not_block_each_other() -> None:
    import asyncio

    order: list[str] = []

    async def handler(dto):
        if dto.zone_id == "zone-slow":
            await asyncio.sleep(0.05)
        order.append(dto.zone_id)

    router = EventRouter(handler)
    raw_slow = make_agent_result(
        result_type="worker_analysis", zone_id="zone-slow", payload={"worker_id": "W-1"}, event_id="s1"
    )
    raw_fast = make_agent_result(
        result_type="worker_analysis", zone_id="zone-fast", payload={"worker_id": "W-2"}, event_id="f1"
    )

    await asyncio.gather(
        router.route("sentinel.worker.analysis.v1", raw_slow),
        router.route("sentinel.worker.analysis.v1", raw_fast),
    )

    # The fast zone's handler completes before the slow zone's, proving no
    # cross-zone lock was taken (Phase 2.2 §13.4).
    assert order[0] == "zone-fast"


async def test_handler_exception_is_retried_then_absorbed_never_crashes_router() -> None:
    attempts = {"count": 0}

    async def flaky_handler(dto):
        attempts["count"] += 1
        raise RuntimeError("transient failure")

    router = EventRouter(flaky_handler)
    raw = make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})

    await router.route("sentinel.worker.analysis.v1", raw)  # must not raise

    assert attempts["count"] == 3
    assert router.metrics.handler_failures_total == 1
