"""
environmental_agent_worker.py

B1 status update: this worker previously existed as a workaround BECAUSE
agents/environmental-intelligence-agent/main.py could not start AgentRunner
(no legal output_topic -- see CODEGEN_REPAIR_REPORT.md). That guard is now
removed and main.py runs a real AgentRunner directly, so this file now
mirrors zone_agent_worker.py's pattern exactly instead of hand-rolling its
own poll loop: real AgentRunner, TracingTransport-wrapped real KafkaTransport,
and an _ObservedEnvironmentalAgent that logs what process() actually
returned (EnvironmentAnalysis published, or None -- e.g. gas-only zone
readings, still B3-blocked, see environmental_intelligence_agent.py's
process() docstring) before AgentRunner publishes it.

Usage:
    python3 environmental_agent_worker.py [--max-iterations N] [--max-empty-polls N]
"""
from __future__ import annotations

import argparse
import sys

import harness_config as cfg

cfg.bootstrap_agent_sys_path(cfg.ENV_AGENT_DIR)

from sentinel_agent_sdk import AgentRunner  # noqa: E402
from sentinel_contracts.agent_contracts.environment_analysis_v1 import EnvironmentAnalysisV1  # noqa: E402
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

import main as env_main  # noqa: E402  -- the agent's own main.py, reused unmodified
from environmental_intelligence_agent import EnvironmentalIntelligenceAgent  # noqa: E402

from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402


class _ObservedEnvironmentalAgent(EnvironmentalIntelligenceAgent):
    """Observation-only: logs one extra stage row after the real process()
    call so the trace dashboard shows *why* a given SensorEvent did or
    didn't produce output, without changing what process() returns or how
    AgentRunner publishes it. Mirrors zone_agent_worker.py's
    _ObservedZoneAgent -- same non-interference pattern, applied here."""

    def process(self, event):
        event_type = type(event).__name__
        trace_id = getattr(event, "trace_id", None)
        correlation_id = str(getattr(event, "correlation_id", "") or "") or None
        event_id = str(getattr(event, "event_id", "") or "") or None

        result = super().process(event)  # the real logic, executed exactly once

        if isinstance(result, EnvironmentAnalysisV1):
            log_stage(StageEvent(
                component="Environmental Agent", stage="EnvironmentAnalysis Computed",
                status="success", trace_id=trace_id, correlation_id=correlation_id,
                event_id=event_id, event_type=event_type,
                extra={"risk_score": result.payload.risk_score,
                       "hazard_types": [h.hazard_type.value if h.hazard_type else None
                                        for h in result.payload.hazards]},
            ))
        elif result is None:
            log_stage(StageEvent(
                component="Environmental Agent", stage="No Output (see reason)",
                status="skipped", trace_id=trace_id, correlation_id=correlation_id,
                event_id=event_id, event_type=event_type,
                reason=("Non-SensorEventV1 input, or zone snapshot has only GAS "
                        "readings so far -- gas-species fields are unreachable from "
                        "real SensorEvent traffic (B3), see sensor_snapshot_aggregator.py"),
            ))
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-empty-polls", type=int, default=None)
    parser.add_argument("--poll-timeout", type=float, default=0.5)
    args = parser.parse_args()

    schema_provider = LocalSchemaProvider()

    producer_transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="environmental-intelligence-agent-producer"),
        component="Environmental Agent",
    )
    producer = EventProducer(producer_transport, schema_provider)

    consumer_transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="environmental-intelligence-agent-consumer"),
        component="Environmental Agent",
    )
    consumer = EventConsumer(
        consumer_transport, schema_provider, env_main.EVENT_TYPES,
        group_id=cfg.CONSUMER_GROUP_ENV_AGENT,
    )

    state = env_main.build_state_container()
    agent = _ObservedEnvironmentalAgent()
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=env_main.INPUT_TOPICS, output_topic=cfg.TOPIC_ENVIRONMENT_ANALYSIS,
    )

    print(f"[Environmental Agent] consuming {env_main.INPUT_TOPICS} as group={cfg.CONSUMER_GROUP_ENV_AGENT}")
    try:
        runner.run(
            poll_timeout_seconds=args.poll_timeout,
            max_iterations=args.max_iterations,
            max_empty_polls=args.max_empty_polls,
        )
    except KeyboardInterrupt:
        runner.request_shutdown()
        runner.drain()
    print("[Environmental Agent] stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
