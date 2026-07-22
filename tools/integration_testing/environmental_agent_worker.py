"""
environmental_agent_worker.py

Drives the REAL EnvironmentalIntelligenceAgent (agents/environmental-
intelligence-agent/environmental_intelligence_agent.py, imported unmodified)
against real Kafka traffic on sentinel.sensor.events.v1, using the real
EventConsumer/KafkaTransport/LocalSchemaProvider.

Why this doesn't go through AgentRunner, and why that's not a workaround
invented for this harness -- it's the path the agent's own main.py already
documents: main.py raises RuntimeError before AgentRunner.run() ever
executes, because sentinel.environment.analysis.v1 (schema
environment_analysis) has no generated Pydantic model anywhere in the repo
(B1) -- AgentRunner.__init__ requires a legal output_topic/output_topics,
and there is no legal one to give it. main.py's own comment says exactly
what to do instead: "construct EnvironmentalIntelligenceAgent +
SensorSnapshotAggregator directly and drive them from a script -- not
through this main()." That is precisely what this file does -- nothing
about EnvironmentalIntelligenceAgent, engine/*, or sensor_snapshot_
aggregator.py is changed; only the wiring differs from main.py's.

What actually happens per event today (verified by reading process(),
not assumed): SensorEvent -> SensorSnapshotAggregator.ingest() (real,
runs) -> process() returns None. The 18-step engine pipeline
(Threshold/Trend/Prediction/Correlation/Risk/Recommendation/...) is fully
constructed in initialize() but NEVER CALLED from process() as of this
codebase -- see that method's own docstring for exactly why (B1 + B3).
This worker reports that honestly: one stage row for the aggregation that
DOES run, one explicit "skipped, here's why" row for the engine services
that don't, one for the publish that can't happen. No fabricated
Threshold/Risk/etc. SUCCESS rows.

Usage:
    python3 environmental_agent_worker.py [--max-iterations N] [--max-empty-polls N]
"""
from __future__ import annotations

import argparse
import sys

import harness_config as cfg

cfg.bootstrap_agent_sys_path(cfg.ENV_AGENT_DIR)

from sentinel_agent_sdk.container import build_container  # noqa: E402
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402
from sentinel_state import StateContainer  # noqa: E402

import main as env_main  # noqa: E402  -- the agent's own main.py, imported for its INPUT_TOPICS/EVENT_TYPES only
from environmental_intelligence_agent import EnvironmentalIntelligenceAgent  # noqa: E402

from event_logger import StageEvent, log_stage, timed_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

ENGINE_SERVICES_SKIPPED_REASON = (
    "Not invoked by process() in the current codebase -- process() stops after "
    "SensorSnapshotAggregator.ingest() and returns None. ThresholdService, TrendService, "
    "PredictionService, CorrelationService, RiskService, RecommendationService, and the "
    "rest of the 18-step engine pipeline are constructed in initialize() but never called. "
    "See environmental_intelligence_agent.py's process() docstring (B1: no "
    "EnvironmentAnalysis model to ever publish; B3: gas-species disambiguation unreachable)."
)
PUBLISH_SKIPPED_REASON = (
    "B1: sentinel.environment.analysis.v1 (schema environment_analysis) has no generated "
    "Pydantic model anywhere in the repo. See agents/environmental-intelligence-agent/"
    "main.py's RuntimeError -- AgentRunner refuses to start over this exact gap."
)


def make_handler(agent: EnvironmentalIntelligenceAgent):
    def handler(event):
        trace_id = getattr(event, "trace_id", None)
        correlation_id = str(getattr(event, "correlation_id", "") or "") or None
        event_id = str(getattr(event, "event_id", "") or "") or None
        event_type = type(event).__name__

        with timed_stage(
            "Environmental Agent", "SensorSnapshotAggregator Ingest",
            trace_id=trace_id, correlation_id=correlation_id, event_id=event_id, event_type=event_type,
        ):
            agent.process(event)

        log_stage(StageEvent(
            component="Environmental Agent",
            stage="Engine Services (Threshold/Trend/Prediction/Correlation/Risk/Recommendation/...)",
            status="skipped", trace_id=trace_id, correlation_id=correlation_id, event_id=event_id,
            event_type=event_type, reason=ENGINE_SERVICES_SKIPPED_REASON,
        ))
        log_stage(StageEvent(
            component="Environmental Agent", stage="EnvironmentAnalysis Publish",
            status="skipped", trace_id=trace_id, correlation_id=correlation_id, event_id=event_id,
            event_type=event_type, topic=cfg.TOPIC_ENVIRONMENT_ANALYSIS, reason=PUBLISH_SKIPPED_REASON,
        ))
        return None
    return handler


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
    producer = EventProducer(producer_transport, schema_provider)  # constructed for container parity; process()
    # never returns a result today, so publish() is never actually called -- see module docstring.

    consumer_transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS,
                        client_id="environmental-intelligence-agent-consumer"),
        component="Environmental Agent",
    )
    consumer = EventConsumer(
        consumer_transport, schema_provider, env_main.EVENT_TYPES,
        group_id=cfg.CONSUMER_GROUP_ENV_AGENT,
    )

    state = StateContainer()  # same as env_main.build_state_container(): no backend fits yet, degrades gracefully
    agent = EnvironmentalIntelligenceAgent()
    agent.container = build_container("EnvironmentalIntelligenceAgent", state, producer)
    agent.initialize()

    consumer.subscribe(env_main.INPUT_TOPICS, handler=make_handler(agent))

    print(f"[Environmental Agent] consuming {env_main.INPUT_TOPICS} as group={cfg.CONSUMER_GROUP_ENV_AGENT}")
    iterations = 0
    empty_polls = 0
    try:
        while True:
            outcome = consumer.poll_once(args.poll_timeout)
            if outcome is None:
                empty_polls += 1
            else:
                empty_polls = 0
                iterations += 1
                log_stage(StageEvent(component="Environmental Agent", stage="Handler Outcome",
                                      status="success" if outcome.status == "success" else "failed",
                                      reason=None if outcome.status == "success" else outcome.status,
                                      extra={"destination_topic": outcome.destination_topic}))
            if args.max_iterations is not None and iterations >= args.max_iterations:
                break
            if args.max_empty_polls is not None and empty_polls >= args.max_empty_polls:
                break
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        producer.close()
    print(f"[Environmental Agent] stopped after {iterations} processed event(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
