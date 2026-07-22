from __future__ import annotations

from risk_orchestrator_agent.application.scoring_pipeline import OperationalContextPipeline
from risk_orchestrator_agent.domain.context.context_builder import ContextBuilder
from risk_orchestrator_agent.domain.correlation.correlation_engine import CorrelationEngine
from risk_orchestrator_agent.dto.agent_result_dto import AgentResultDTO
from risk_orchestrator_agent.memory.adapters.redis_context_adapter import RedisContextAdapter
from risk_orchestrator_agent.services.context_replay_service import ContextReplayService
from tests.unit.conftest import make_agent_result


async def test_pipeline_produces_correlated_snapshot_and_records_history(fake_redis) -> None:
    adapter = RedisContextAdapter(fake_redis)
    pipeline = OperationalContextPipeline(
        context_builder=ContextBuilder(context_port=adapter),
        correlation_engine=CorrelationEngine(),
        replay_service=ContextReplayService(adapter),
    )

    dto = AgentResultDTO.from_raw(
        make_agent_result(
            result_type="environment_analysis",
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
        )
    )

    result = await pipeline.handle(dto)

    assert result.sensor is not None
    assert result.sensor.hazards[0].hazard_type == "toxic_gas"
    assert pipeline.metrics.cycles_total == 1
    assert pipeline.metrics.context_build_time_ms_last >= 0
    assert pipeline.metrics.snapshot_time_ms_last >= 0
    assert pipeline.metrics.correlation_time_ms_last >= 0

    history = await ContextReplayService(adapter).history(dto.zone_id)
    assert len(history) == 1


async def test_pipeline_never_produces_a_risk_score_or_severity(fake_redis) -> None:
    """No risk scoring or decisioning should be produced yet (this
    phase's explicit non-goal)."""
    adapter = RedisContextAdapter(fake_redis)
    pipeline = OperationalContextPipeline(
        context_builder=ContextBuilder(context_port=adapter),
        correlation_engine=CorrelationEngine(),
    )
    dto = AgentResultDTO.from_raw(
        make_agent_result(result_type="worker_analysis", payload={"worker_id": "W-1"})
    )
    result = await pipeline.handle(dto)

    assert not hasattr(result, "score")
    assert not hasattr(result, "severity")
    assert not hasattr(result, "decision_category")
