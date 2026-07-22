from __future__ import annotations

import dataclasses

from risk_orchestrator_agent.domain.correlation.correlation_engine import CorrelationEngine
from risk_orchestrator_agent.domain.models.correlation_finding import CorrelationType
from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter
from tests.unit.conftest import make_agent_result


async def _build_context(fake_redis, zone_id="zone-17"):
    adapter = RedisContextAdapter(fake_redis)
    builder = ContextBuilder(context_port=adapter)
    await builder.update(
        zone_id,
        AgentResultDTO.from_raw(
            make_agent_result(
                result_type="zone_analysis",
                zone_id=zone_id,
                payload={"zone_state": "warning", "equipment_ids": ["EQ-1"]},
                event_id="e1",
            )
        ),
    )
    await builder.update(
        zone_id,
        AgentResultDTO.from_raw(
            make_agent_result(
                result_type="worker_analysis",
                zone_id=zone_id,
                payload={"worker_id": "W-1", "zone_clearance": True},
                event_id="e2",
            )
        ),
    )
    await builder.update(
        zone_id,
        AgentResultDTO.from_raw(
            make_agent_result(
                result_type="permit_analysis",
                zone_id=zone_id,
                payload={"permit_id": "P-1", "zone_compatibility": True},
                event_id="e3",
            )
        ),
    )
    await builder.update(
        zone_id,
        AgentResultDTO.from_raw(
            make_agent_result(
                result_type="environment_analysis",
                zone_id=zone_id,
                payload={
                    "hazards": [
                        {
                            "hazard_type": "toxic_gas",
                            "measured_value": 38.5,
                            "unit": "ppm",
                            "threshold_ppm": 35,
                            "threshold_breach": True,
                            "trend": "rising",
                        }
                    ]
                },
                event_id="e4",
            )
        ),
    )
    return await builder.snapshot(zone_id)


async def test_correlation_engine_discovers_worker_zone_relationship(fake_redis) -> None:
    context = await _build_context(fake_redis)
    engine = CorrelationEngine()
    findings = engine.correlate(context)
    types_found = {f.correlation_type for f in findings}
    assert CorrelationType.WORKER_ZONE in types_found
    assert CorrelationType.WORKER_PERMIT in types_found
    assert CorrelationType.PERMIT_ZONE in types_found
    assert CorrelationType.ENVIRONMENT_ZONE in types_found


async def test_correlation_engine_never_judges_risk(fake_redis) -> None:
    """CorrelationEngine's findings carry strength/confidence and a
    structural summary — never a severity or risk classification field
    (Phase 2.3 §1.4)."""
    context = await _build_context(fake_redis)
    engine = CorrelationEngine()
    for finding in engine.correlate(context):
        assert not hasattr(finding, "severity")
        assert not hasattr(finding, "decision_category")
        assert 0.0 <= finding.strength <= 1.0
        assert 0.0 <= finding.confidence <= 1.0


async def test_correlate_and_attach_preserves_context_immutability(fake_redis) -> None:
    context = await _build_context(fake_redis)
    engine = CorrelationEngine()
    correlated = engine.correlate_and_attach(context)
    assert correlated.zone_id == context.zone_id
    assert correlated.correlation_findings != context.correlation_findings
    assert len(correlated.correlation_findings) > 0
    # Original snapshot object is untouched (frozen dataclass, Phase 2.2 §5.4).
    assert context.correlation_findings == ()


def test_no_findings_when_context_is_empty() -> None:
    from risk_orchestrator_agent.domain.context.context_builder import _empty_context

    engine = CorrelationEngine()
    findings = engine.correlate(_empty_context("zone-x", "site-04"))
    assert findings == []
