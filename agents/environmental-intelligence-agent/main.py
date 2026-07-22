"""
main.py

Environmental Intelligence Agent's entrypoint. Per sentinel_agent_sdk's
design (base_agent.py's module docstring), a conforming agent's main.py
is wiring only -- no business logic lives here. All business logic is in
engine/*.py, preserved verbatim from the standalone gas-intelligence-agent
service.

CROSS-CHECK NOTE (repository code vs. what actually runs): zone_intelligence
_agent/main.py -- this repository's fullest working reference -- calls
`KafkaTransport(client_id="...")` with no `bootstrap_servers` argument.
sentinel_eventbus/kafka_transport.py's KafkaTransport.__init__ has no
default for `bootstrap_servers`; that call site would raise a TypeError
the moment it actually ran against real Kafka. This file does NOT
replicate that -- bootstrap_servers is read from KAFKA_BOOTSTRAP_SERVERS
(same env var name pattern zone_intelligence_agent uses for its own
Redis/Postgres/Neo4j/Qdrant connection info) so this agent actually
starts. Flagged here rather than silently diverging from the reference
without comment.

KNOWN GAPS (tracked, not worked around -- see migration report §0):
  B1: sentinel.environment.analysis.v1 has no publishable generated model.
      This agent cannot be started via AgentRunner.run() until B1
      resolves -- see the RuntimeError at the bottom of main().
  B2: sentinel.environmental.events.v1 (schema `environmental_event`) has
      no generated model to register in EVENT_TYPES. Left commented out
      in INPUT_TOPICS/EVENT_TYPES below.
  B3: SensorEvent(sensor_type=GAS) cannot be disambiguated into individual
      gas species. Handled inside sensor_snapshot_aggregator.py, not here.
"""
from __future__ import annotations

import os

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider
from sentinel_state import StateContainer

from environmental_intelligence_agent import EnvironmentalIntelligenceAgent

# Topic names taken verbatim from contracts/topics/kafka_topics.yaml --
# never a locally invented string (see migration report, requirement 5).
INPUT_TOPICS = [
    "sentinel.sensor.events.v1",
    # "sentinel.environmental.events.v1",  # BLOCKED: B2 -- environmental_event
    #  has no Avro source under contracts/events/, so there is no model to
    #  register in EVENT_TYPES below. Re-add both lines together once B2
    #  lands.
]

EVENT_TYPES = {
    "SensorEvent": SensorEventV1,
    # "EnvironmentalEvent": ...,  # BLOCKED: B2
}


def build_state_container() -> StateContainer:
    """No repository in sentinel_state fits "recent environmental readings
    per zone" yet (checked ZoneStateRepository, WorkerPresenceRepository,
    AnomalyTrackingRepository, StateChangeTrackingRepository,
    IncidentTrackingRepository -- none match). engine/history_manager.py's
    in-memory HistoryManager is used directly by
    EnvironmentalIntelligenceAgent instead (see that file and the
    migration report). StateContainer is constructed with no backends
    configured; per its own module docstring this degrades gracefully --
    an agent that uses none of Redis/Postgres/Neo4j/Qdrant doesn't get any
    of those clients spun up."""
    return StateContainer()


def build_kafka_transport(client_id: str) -> KafkaTransport:
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    return KafkaTransport(bootstrap_servers=bootstrap_servers, client_id=client_id)


def main() -> None:
    schema_provider = LocalSchemaProvider()
    producer = EventProducer(
        build_kafka_transport("environmental-intelligence-agent-producer"), schema_provider
    )
    consumer = EventConsumer(
        build_kafka_transport("environmental-intelligence-agent-consumer"),
        schema_provider, EVENT_TYPES, group_id="environmental-intelligence-agent",
    )
    state = build_state_container()
    agent = EnvironmentalIntelligenceAgent()

    # BLOCKED: B1. AgentRunner.__init__ requires output_topic and/or
    # output_topics (raises ValueError otherwise -- see runner.py). There
    # is no legal value to pass: sentinel.environment.analysis.v1 is the
    # only topic this agent's registry entry authorizes it to produce to,
    # and publishing to it requires a resolvable EnvironmentAnalysis
    # model, which does not exist (see migration report §0, B1). Passing
    # the topic name anyway, while process() always returns None today,
    # would silently arm this agent to publish EnvironmentAnalysis-shaped
    # data to a real topic the instant someone re-enables the pipeline in
    # environmental_intelligence_agent.process() without re-checking B1 --
    # that is exactly the kind of latent landmine this migration is
    # supposed to avoid. Fail loudly instead.
    raise RuntimeError(
        "environmental_intelligence_agent cannot start via AgentRunner yet: "
        "sentinel.environment.analysis.v1 has no publishable generated model "
        "(migration report B1). Resolve B1 (and B2, B3 for full gas-hazard "
        "coverage) before deploying. To validate the consume/aggregate path "
        "against live sentinel.sensor.events.v1 traffic in the meantime, "
        "construct EnvironmentalIntelligenceAgent + SensorSnapshotAggregator "
        "directly and drive them from a script -- not through this main()."
    )

    # Unreachable until B1 resolves -- left in place, not deleted, so the
    # normal startup path is a one-line change (delete the RuntimeError
    # above) once it does:
    runner = AgentRunner(  # noqa: F841 (unreachable by design, see above)
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=INPUT_TOPICS, output_topic="sentinel.environment.analysis.v1",
    )
    runner.run()


if __name__ == "__main__":
    main()
