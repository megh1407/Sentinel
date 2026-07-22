"""
zone_agent_worker.py

Unlike the environmental agent, Zone Intelligence Agent's own main.py is
NOT blocked -- it constructs and runs a real AgentRunner today. This
worker reuses that exact wiring (imports agents/zone_intelligence_agent/
main.py's INPUT_TOPICS, OUTPUT_TOPICS, EVENT_TYPES, build_state_container,
and _ZoneAnomalySuppressingAgent unmodified) and only adds two
purely-observational layers on top:

  1. TracingTransport wraps the real KafkaTransport (see that file) so
     every produce/poll/commit is recorded -- no different from what's
     done for every other worker/simulator in this harness.
  2. _ObservedZoneAgent subclasses _ZoneAnomalySuppressingAgent to log
     what process() actually computed BEFORE that class strips
     ZoneAnomalyDetectedV1 results from what reaches Kafka. This does not
     change what gets published -- _ZoneAnomalySuppressingAgent.process()
     runs exactly as main.py wrote it; the subclass only reads its return
     value and calls super(). Reported honestly: ZoneState really is
     published to sentinel.zone.state.v1; ZoneAnomalyDetected is real,
     computed, Postgres-audited (per that class's own docstring) -- but
     never published, because kafka_topics.yaml has no output topic
     registered for it (PLATFORM_GAP, documented in main.py's docstring,
     not something this harness invented).

sentinel.zone.analysis.v1 is registered in kafka_topics.yaml
(schema: zone_analysis) but has no generated model anywhere in the repo
either (grep -rl "class ZoneAnalysis" returns nothing) and main.py never
wires it -- this worker does not fabricate a message for it.

Usage:
    python3 zone_agent_worker.py [--max-iterations N] [--max-empty-polls N]
"""
from __future__ import annotations

import argparse
import sys

import harness_config as cfg

cfg.bootstrap_agent_sys_path(cfg.ZONE_AGENT_DIR)

from sentinel_agent_sdk import AgentRunner  # noqa: E402
from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1  # noqa: E402
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1  # noqa: E402
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider  # noqa: E402

import main as zone_main  # noqa: E402  -- the agent's own main.py, reused unmodified

from event_logger import StageEvent, log_stage  # noqa: E402
from tracing_transport import TracingTransport  # noqa: E402

ZONE_ANOMALY_UNPUBLISHED_REASON = (
    "ZoneAnomalyDetected is real and fully computed (Postgres audit rows written, "
    "zone_anomalies_detected_total incremented) but never published to Kafka: "
    "kafka_topics.yaml has no output topic registered for it, so main.py's own "
    "_ZoneAnomalySuppressingAgent strips it before AgentRunner would otherwise crash "
    "trying to publish to a topic that doesn't exist. See main.py's module docstring."
)


class _ObservedZoneAgent(zone_main.ZoneIntelligenceAgent):
    """Observation-only. Deliberately subclasses ZoneIntelligenceAgent
    directly rather than main.py's _ZoneAnomalySuppressingAgent: that
    class's process() is `results = super().process(event); return
    filtered`, and calling it via super() AFTER already calling the real
    process() once ourselves would run the real business logic TWICE per
    event -- double Redis/Postgres writes, and (worse) it would silently
    corrupt the false->true anomaly transition guards the real logic
    depends on, since the second call would see state the first call just
    changed. So process() below calls the real logic exactly once, then
    applies the SAME one-line filter _ZoneAnomalySuppressingAgent applies
    (`[r for r in results if not isinstance(r, ZoneAnomalyDetectedV1)]`,
    copied verbatim from that class, not reinterpreted) before returning --
    same net behavior, zero double-execution risk.

    PLATFORM_GAP reminder (unchanged from main.py): delete this subclass's
    filtering and use plain ZoneIntelligenceAgent() the moment
    kafka_topics.yaml registers a real output topic for ZoneAnomalyDetected.
    """

    def process(self, event):
        event_type = type(event).__name__
        trace_id = getattr(event, "trace_id", None)
        correlation_id = str(getattr(event, "correlation_id", "") or "") or None
        event_id = str(getattr(event, "event_id", "") or "") or None

        raw_results = super().process(event)  # the real logic, executed exactly once

        for r in (raw_results or []):
            if isinstance(r, ZoneStateV1):
                log_stage(StageEvent(
                    component="Zone Agent", stage="ZoneState Computed", status="success",
                    trace_id=trace_id, correlation_id=correlation_id, event_id=event_id, event_type=event_type,
                ))
            elif isinstance(r, ZoneAnomalyDetectedV1):
                log_stage(StageEvent(
                    component="Zone Agent", stage="ZoneAnomalyDetected Computed (not published)",
                    status="skipped", trace_id=trace_id, correlation_id=correlation_id, event_id=event_id,
                    event_type=event_type, reason=ZONE_ANOMALY_UNPUBLISHED_REASON,
                    extra={"anomaly_type": getattr(getattr(r, "payload", None), "anomaly_type", None)},
                ))
        if raw_results is None:
            return None
        # Same filter as main.py's _ZoneAnomalySuppressingAgent.process(), copied verbatim:
        filtered = [r for r in raw_results if not isinstance(r, ZoneAnomalyDetectedV1)]
        return filtered or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-empty-polls", type=int, default=None)
    parser.add_argument("--poll-timeout", type=float, default=0.5)
    args = parser.parse_args()

    schema_provider = LocalSchemaProvider()

    producer_transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS, client_id="zone-intelligence-agent-producer"),
        component="Zone Agent",
    )
    producer = EventProducer(producer_transport, schema_provider)

    consumer_transport = TracingTransport(
        KafkaTransport(bootstrap_servers=cfg.KAFKA_BOOTSTRAP_SERVERS, client_id="zone-intelligence-agent-consumer"),
        component="Zone Agent",
    )
    consumer = EventConsumer(
        consumer_transport, schema_provider, zone_main.EVENT_TYPES, group_id=cfg.CONSUMER_GROUP_ZONE_AGENT,
    )

    state = zone_main.build_state_container()  # real Redis (required) + optional Postgres, unmodified
    agent = _ObservedZoneAgent()
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=zone_main.INPUT_TOPICS, output_topics=zone_main.OUTPUT_TOPICS,
    )

    print(f"[Zone Agent] consuming {zone_main.INPUT_TOPICS} as group={cfg.CONSUMER_GROUP_ZONE_AGENT}")
    try:
        runner.run(
            poll_timeout_seconds=args.poll_timeout,
            max_iterations=args.max_iterations,
            max_empty_polls=args.max_empty_polls,
        )
    except KeyboardInterrupt:
        runner.request_shutdown()
        runner.drain()
    print("[Zone Agent] stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
