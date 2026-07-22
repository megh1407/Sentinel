from __future__ import annotations

import pytest

from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
from risk_orchestrator_agent.domain.exceptions import ContextValidationError
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter
from tests.unit.conftest import make_agent_result


@pytest.fixture
def builder(fake_redis) -> ContextBuilder:
    adapter = RedisContextAdapter(fake_redis)
    return ContextBuilder(context_port=adapter)


async def test_first_event_for_new_zone_creates_context(builder: ContextBuilder) -> None:
    dto = AgentResultDTO.from_raw(
        make_agent_result(
            result_type="worker_analysis",
            payload={"worker_id": "W-33210", "safety_status": "at_risk", "ppe_compliance": 0.5},
        )
    )
    updated = await builder.update("zone-17", dto)
    assert len(updated.workers) == 1
    assert updated.workers[0].worker_id == "W-33210"


async def test_snapshot_of_never_seen_zone_has_all_domains_missing(builder: ContextBuilder) -> None:
    snapshot = await builder.snapshot("zone-never-seen")
    assert set(snapshot.quality.missing_domains) == {
        "worker", "zone", "equipment", "permit", "sensor", "incident", "maintenance",
    }
    assert snapshot.quality.completeness == 0.0


async def test_merge_preserves_other_domains_untouched(builder: ContextBuilder) -> None:
    worker_dto = AgentResultDTO.from_raw(
        make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"}, event_id="e1")
    )
    zone_dto = AgentResultDTO.from_raw(
        make_agent_result(result_type="zone_analysis", payload={"zone_state": "warning"}, event_id="e2")
    )
    await builder.update("zone-17", worker_dto)
    await builder.update("zone-17", zone_dto)
    snapshot = await builder.snapshot("zone-17")
    assert snapshot.zone is not None
    assert snapshot.zone.zone_state == "warning"
    assert len(snapshot.workers) == 1  # worker data from the first event is retained


async def test_maintenance_overdue_tasks_are_tracked_per_equipment(builder: ContextBuilder) -> None:
    eq1 = AgentResultDTO.from_raw(
        make_agent_result(
            result_type="maintenance_analysis",
            payload={"equipment_id": "EQ-1", "active_faults": ["overheat"]},
            event_id="e-eq-1",
        )
    )
    second = AgentResultDTO.from_raw(
        make_agent_result(
            result_type="maintenance_analysis",
            payload={"equipment_id": "EQ-1", "overdue_tasks": ["lubrication"]},
            event_id="e-eq-2",
        )
    )
    await builder.update("zone-17", eq1)
    await builder.update("zone-17", second)
    snapshot = await builder.snapshot("zone-17")

    assert len(snapshot.maintenance) == 1
    assert "lubrication" in snapshot.maintenance[0].overdue_tasks

    # EquipmentContext's active_faults accumulate additively (Phase 2.2 §4.2,
    # §3): the second event doesn't mention "overheat" but must not drop it.
    assert len(snapshot.equipment) == 1
    assert "overheat" in snapshot.equipment[0].active_faults


async def test_validation_error_when_populated_context_has_no_evidence(fake_redis) -> None:
    # Construct a ContextBuilder against a pre-populated (evidence-less)
    # rolling context to exercise the hard-validation path directly.
    from risk_orchestrator_agent.domain.context.context_builder import _empty_context
    import dataclasses

    adapter = RedisContextAdapter(fake_redis)
    builder = ContextBuilder(context_port=adapter)

    from risk_orchestrator_agent.domain.models.zone_context import ZoneContext
    from risk_orchestrator_agent.domain.models.confidence import Age, ConfidenceScore
    from datetime import timedelta
    from risk_orchestrator_agent.utils.time_utils import utcnow

    broken = dataclasses.replace(
        _empty_context("zone-x", "site-04"),
        zone=ZoneContext(
            zone_id="zone-x",
            site_id="site-04",
            zone_state="warning",
            risk_factors=(),
            anomalies=(),
            worker_count=None,
            equipment_ids=(),
            confidence=ConfidenceScore(0.9),
            analyzed_at=utcnow(),
            age=Age(timedelta(seconds=1)),
        ),
    )
    await adapter.put("zone-x", broken)

    with pytest.raises(ContextValidationError):
        await builder.snapshot("zone-x")


async def test_redis_unavailable_degrades_to_created_state_not_a_hard_failure(fake_redis) -> None:
    fake_redis.fail = True
    adapter = RedisContextAdapter(fake_redis)
    builder = ContextBuilder(context_port=adapter)
    snapshot = await builder.snapshot("zone-99")
    assert snapshot.quality.completeness == 0.0
