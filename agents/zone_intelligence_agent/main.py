"""
main.py

Zone Intelligence Agent's entrypoint. Per sentinel_agent_sdk's design (see
runner.py's module docstring), a conforming agent's entire main.py is just
wiring AgentRunner together -- no business logic lives here.

This wires REAL backends (Redis, Postgres, and optionally Neo4j/Qdrant),
not the in-memory test doubles the test suite uses -- run this in an
environment with those reachable, or with the optional backends' env vars
unset (StateContainer degrades gracefully -- see its docstring).

TOPIC WIRING -- aligned to the frozen registry (contracts/agent-registry/
agents.yaml + contracts/topics/kafka_topics.yaml) as of the Phase 1.5
re-verification pass, NOT to zone_intelligence_agent.py's earlier ad-hoc
topic strings (sensor.events.raw, zone.state.updated, etc.), which never
matched kafka_topics.yaml's sentinel.{domain}.{type}.v{n} convention (see
AGENT_GUIDE.md) and have been retired from this file. Every topic below is
one this agent is registered to consume/produce as of that pass.

# PLATFORM_GAP -- three items zone_intelligence_agent.py's business logic
# still fully implements are NOT wired to Kafka here, because the frozen
# registry has no topic for them yet:
#   - EquipmentRiskDetected (consume): real contract
#     (sentinel_contracts.events.equipment_risk_detected_v1), but no
#     kafka_topics.yaml entry exists for it under any name.
#   - MaintenanceRequired (consume): same situation -- real contract, no
#     registered topic.
#   - ZoneAnomalyDetected (produce): real contract, but the registry's
#     only related entry (sentinel.zone.analysis.v1 / schema zone_analysis)
#     has no matching contract anywhere in the repo, and
#     zone.anomaly.detected was never registered under its own name either.
# IncidentEvent (consume) is ALSO left unwired here: sentinel.incident.events.v1
# does exist and IS registered, but zone_intelligence_agent is not yet listed
# as one of its consumers in kafka_topics.yaml, and no architecture document
# (AGENT_GUIDE.md included) confirms this agent as an approved consumer of
# it -- only this agent's own code did. Per the Phase 1.5 re-verification
# pass, code-only evidence isn't sufficient to register it, so it's grouped
# with the other PLATFORM_GAP items pending architect confirmation.
#
# None of this deletes anything: the four event classes are still imported
# and handled by zone_intelligence_agent.py's process() exactly as before
# (see the PLATFORM_GAP notes there), and _ZoneAnomalySuppressingAgent below
# only trims ZoneAnomalyDetectedV1 off the RESULT of process() -- the
# detection logic, Postgres persistence, and metrics inside process() still
# run every time. Re-enabling any of the four is then just: (1) add the
# topic to kafka_topics.yaml + agents.yaml, (2) add it back to INPUT_TOPICS/
# EVENT_TYPES or OUTPUT_TOPICS below, (3) delete _ZoneAnomalySuppressingAgent
# and go back to plain ZoneIntelligenceAgent() once ZoneAnomalyDetected has
# a registered topic.
"""
from __future__ import annotations

import os

from sentinel_agent_sdk import AgentRunner
from sentinel_contracts.events.permit_event_v1 import PermitEventV1
from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
from sentinel_contracts.events.worker_event_v1 import WorkerEventV1
from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1
from sentinel_eventbus import EventConsumer, EventProducer, KafkaTransport, LocalSchemaProvider
from sentinel_state import StateContainer, build_engine, build_session_factory
from sentinel_state.postgres_repositories import ZoneRepository

from zone_intelligence_agent import ZoneIntelligenceAgent

INPUT_TOPICS = [
    "sentinel.sensor.events.v1",
    "sentinel.worker.events.v1",
    "sentinel.permit.events.v1",
    # PLATFORM_GAP: sentinel.equipment.state.v1 is also in this agent's
    # agents.yaml `consumes` entry, but no generated Pydantic model exists
    # for its `equipment_state` schema anywhere in sentinel_contracts (only
    # a legacy contracts/events/v1/equipment_state.schema.json file) -- so
    # it cannot be wired here without inventing a model. Not subscribed.
]
OUTPUT_TOPICS = {
    "ZoneState": "sentinel.zone.state.v1",
    # PLATFORM_GAP: "ZoneAnomalyDetected" intentionally has no entry -- see
    # module docstring. _ZoneAnomalySuppressingAgent below keeps AgentRunner
    # from ever needing to look this up.
}
EVENT_TYPES = {
    "SensorEvent": SensorEventV1,
    "WorkerEvent": WorkerEventV1,
    "PermitEvent": PermitEventV1,
    # PLATFORM_GAP: EquipmentRiskDetected, IncidentEvent, MaintenanceRequired
    # deliberately omitted -- see module docstring. Their classes are still
    # imported and handled inside zone_intelligence_agent.py itself; they're
    # just never subscribed to here, so the EventConsumer will never
    # deserialize or dispatch them in production.
}


class _ZoneAnomalySuppressingAgent(ZoneIntelligenceAgent):
    """Wiring-layer-only wrapper -- NOT a business-logic change.

    ZoneIntelligenceAgent.process() (zone_intelligence_agent.py) is left
    completely untouched: it still computes and returns ZoneAnomalyDetectedV1
    for every rule exactly as before, and that's verified directly by
    tests/test_zone_intelligence_agent.py, acceptance_check.py, and demo.py,
    none of which go through this wrapper -- they call
    ZoneIntelligenceAgent.process() (or a plain ZoneIntelligenceAgent
    instance) directly.

    The problem this solves is one layer up: AgentRunner
    (sentinel_agent_sdk/runner.py) raises RuntimeError for any result whose
    event_type isn't a key in output_topics (and no default output_topic is
    set here). Since ZoneAnomalyDetected has no registered topic (see this
    file's docstring), publishing it would crash the running process. This
    wrapper strips ONLY that one result type before AgentRunner ever sees
    it. Everything process() already does for an anomaly -- building the
    ZoneAnomalyDetectedV1, incrementing zone_anomalies_detected_total,
    writing the Postgres audit/anomaly rows via self.state.zone_pg -- still
    happens; only the Kafka publish is suppressed.

    PLATFORM_GAP: delete this class and use plain ZoneIntelligenceAgent()
    in main() below, the moment kafka_topics.yaml registers an output topic
    for ZoneAnomalyDetected -- at that point add it to OUTPUT_TOPICS above
    and this wrapper is no longer needed.
    """

    def process(self, event):
        results = super().process(event)
        if results is None:
            return None
        filtered = [r for r in results if not isinstance(r, ZoneAnomalyDetectedV1)]
        return filtered or None


def build_state_container() -> StateContainer:
    import redis

    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )

    postgres_session_factory = None
    postgres_dsn = os.environ.get("POSTGRES_DSN")
    if postgres_dsn:
        engine = build_engine(postgres_dsn)
        postgres_session_factory = build_session_factory(engine)
        ZoneRepository(postgres_session_factory).ensure_schema()

    # Neo4j and Qdrant are OPTIONAL for this agent -- every rule works with
    # Redis (+ Postgres for durability) alone. Only construct them if
    # explicitly configured, matching StateContainer's "don't require a
    # backend this agent wasn't told to use" design.
    neo4j_driver = None
    neo4j_uri = os.environ.get("NEO4J_URI")
    if neo4j_uri:
        from neo4j import GraphDatabase
        neo4j_driver = GraphDatabase.driver(
            neo4j_uri, auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", ""))
        )

    qdrant_client = None
    qdrant_url = os.environ.get("QDRANT_URL")
    if qdrant_url:
        from qdrant_client import QdrantClient
        qdrant_client = QdrantClient(url=qdrant_url)

    return StateContainer(
        redis_client=redis_client,
        postgres_session_factory=postgres_session_factory,
        neo4j_driver=neo4j_driver,
        qdrant_client=qdrant_client,
    )


def main() -> None:
    schema_provider = LocalSchemaProvider()
    producer = EventProducer(KafkaTransport(client_id="zone-intelligence-agent-producer"), schema_provider)
    consumer = EventConsumer(
        KafkaTransport(client_id="zone-intelligence-agent-consumer"), schema_provider,
        EVENT_TYPES, group_id="zone-intelligence-agent",
    )
    state = build_state_container()
    agent = _ZoneAnomalySuppressingAgent()
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=INPUT_TOPICS, output_topics=OUTPUT_TOPICS,
    )
    runner.run()


if __name__ == "__main__":
    main()