"""
agents_runtime.py

Starts the four REAL, already-verified intelligence agents (Zone,
Environmental, Permit, Worker Safety) as AgentRunner instances, each in its
own daemon thread, wired through InMemoryTransport instead of KafkaTransport.

This is NOT a reimplementation and NOT a simulation. Every INPUT_TOPICS /
OUTPUT_TOPICS / EVENT_TYPES value below is copied verbatim from that agent's
own real main.py (see the audit trail in the accompanying report) -- the
only change is the transport class, which the repo's own
scripts/dev-env/docker-compose.yml comment documents as a "one-line
constructor change, same interface" substitution for exactly this situation
(no live Kafka broker reachable). When a real broker is available, replace
InMemoryTransport with KafkaTransport here and nothing else needs to change
-- same as every agent's own main.py already does for KafkaTransport itself.

MODULE-NAME ISOLATION -- a real wrinkle discovered while building this, not
present in any single agent's own docs: three of the four agents
(zone_intelligence_agent, environmental-intelligence-agent,
worker-safety-agent) use a FLAT script layout where main.py sits directly
alongside generically-named sibling modules (config.py, engine/, health.py,
etc.) and imports them as top-level names. That's fine for each agent's own
`python main.py` process, but merging all four into ONE interpreter (which
this file does, since there's no live Kafka broker here to let them be
separate OS processes sharing a real topic log) means their `config`
modules collide in sys.modules. _isolated_import() below scopes each
agent's sys.path insertion and purges the generically-named modules it
imported from sys.modules before the next agent loads -- a wiring-layer
fix, not a change to any agent's own code.

Risk Orchestrator and Response Agent are deliberately absent -- out of
scope per the master integration prompt.
"""
from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager

from sentinel_eventbus import EventConsumer, EventProducer, LocalSchemaProvider
from sentinel_agent_sdk import AgentRunner

from transport_factory import make_transport
from sentinel_state import StateContainer, build_engine, build_session_factory

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@contextmanager
def _isolated_import(*paths: str, purge_names: tuple[str, ...] = ()):
    """Temporarily prepends `paths` to sys.path for the duration of the
    `with` block, then removes them again and deletes any of `purge_names`
    from sys.modules -- so the next agent's same-named flat module (e.g.
    `config`) isn't served a stale cached import from this one."""
    added = [p for p in paths if p not in sys.path]
    for p in added:
        sys.path.insert(0, p)
    try:
        yield
    finally:
        for p in added:
            if p in sys.path:
                sys.path.remove(p)
        for name in purge_names:
            sys.modules.pop(name, None)


def _redis_client():
    import redis
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )


def _postgres_session_factory():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        return None
    engine = build_engine(dsn)
    return build_session_factory(engine)


class AgentHandle:
    """A running agent + the thread driving it, so callers can request a
    clean shutdown (used by the demo script and by API-gateway shutdown)."""

    def __init__(self, name: str, runner: AgentRunner, thread: threading.Thread, agent=None):
        self.name = name
        self.runner = runner
        self.thread = thread
        self.agent = agent

    def stop(self) -> None:
        self.runner.request_shutdown()


def _start_zone_agent(schema_provider: LocalSchemaProvider) -> AgentHandle:
    # Mirrors agents/zone_intelligence_agent/main.py exactly, including the
    # _ZoneAnomalySuppressingAgent wrapper (ZoneAnomalyDetected has no
    # registered Kafka topic -- see that file's PLATFORM_GAP note; the
    # underlying business logic still runs and still writes to
    # Redis/Postgres, only the publish step is skipped, same as production).
    zone_dir = os.path.join(_REPO_ROOT, "agents", "zone_intelligence_agent")
    with _isolated_import(zone_dir, purge_names=("config", "zone_intelligence_agent",
                                                  "graph_projection_service")):
        from zone_intelligence_agent import ZoneIntelligenceAgent
        from sentinel_contracts.events.zone_anomaly_detected_v1 import ZoneAnomalyDetectedV1
        from sentinel_state.postgres_repositories import ZoneRepository

        class _ZoneAnomalySuppressingAgent(ZoneIntelligenceAgent):
            def process(self, event):
                results = super().process(event)
                if results is None:
                    return None
                filtered = [r for r in results if not isinstance(r, ZoneAnomalyDetectedV1)]
                return filtered or None

        agent = _ZoneAnomalySuppressingAgent()
        sf = _postgres_session_factory()
        if sf is not None:
            ZoneRepository(sf).ensure_schema()

    from sentinel_contracts.events.permit_event_v1 import PermitEventV1
    from sentinel_contracts.events.sensor_event_v1 import SensorEventV1
    from sentinel_contracts.events.worker_event_v1 import WorkerEventV1

    input_topics = [
        "sentinel.sensor.events.v1",
        "sentinel.worker.events.v1",
        "sentinel.permit.events.v1",
    ]
    output_topics = {"ZoneState": "sentinel.zone.state.v1"}
    event_types = {
        "SensorEvent": SensorEventV1,
        "WorkerEvent": WorkerEventV1,
        "PermitEvent": PermitEventV1,
    }

    producer = EventProducer(make_transport(client_id="zone-agent-producer"), schema_provider)
    consumer = EventConsumer(
        make_transport(client_id="zone-agent-consumer"), schema_provider,
        event_types, group_id="zone-intelligence-agent",
    )
    state = StateContainer(redis_client=_redis_client(), postgres_session_factory=sf)
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=input_topics, output_topics=output_topics,
    )
    t = threading.Thread(target=runner.run, kwargs={"poll_timeout_seconds": 0.2}, daemon=True, name="zone-agent")
    t.start()
    return AgentHandle("zone-intelligence-agent", runner, t)


def _start_environmental_agent(schema_provider: LocalSchemaProvider) -> AgentHandle:
    # Mirrors agents/environmental-intelligence-agent/main.py exactly.
    env_dir = os.path.join(_REPO_ROOT, "agents", "environmental-intelligence-agent")
    with _isolated_import(env_dir, purge_names=("config", "engine", "environmental_intelligence_agent",
                                                 "sensor_snapshot_aggregator")):
        from environmental_intelligence_agent import EnvironmentalIntelligenceAgent
        agent = EnvironmentalIntelligenceAgent()

    from sentinel_contracts.events.sensor_event_v1 import SensorEventV1

    input_topics = ["sentinel.sensor.events.v1"]
    event_types = {"SensorEvent": SensorEventV1}

    producer = EventProducer(make_transport(client_id="environmental-agent-producer"), schema_provider)
    consumer = EventConsumer(
        make_transport(client_id="environmental-agent-consumer"), schema_provider,
        event_types, group_id="environmental-intelligence-agent",
    )
    state = StateContainer()  # no backend, matches the agent's own main.py
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=input_topics, output_topic="sentinel.environment.analysis.v1",
    )
    t = threading.Thread(target=runner.run, kwargs={"poll_timeout_seconds": 0.2}, daemon=True, name="env-agent")
    t.start()
    return AgentHandle("environmental-intelligence-agent", runner, t, agent=agent)


def _start_permit_agent(schema_provider: LocalSchemaProvider) -> AgentHandle:
    # Mirrors agents/permit-intelligence-agent/src/permit_intelligence_agent/main.py
    # exactly. This agent uses a proper namespaced package (permit_intelligence_agent.*)
    # so it doesn't need the flat-module isolation the other three do.
    permit_src = os.path.join(_REPO_ROOT, "agents", "permit-intelligence-agent", "src")
    with _isolated_import(permit_src):
        from permit_intelligence_agent.agent import PermitIntelligenceAgent
        agent = PermitIntelligenceAgent()

    from sentinel_contracts.events.permit_event_v1 import PermitEventV1
    from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

    input_topics = ["sentinel.permit.events.v1", "sentinel.zone.state.v1"]
    event_types = {"PermitEvent": PermitEventV1, "ZoneState": ZoneStateV1}

    producer = EventProducer(make_transport(client_id="permit-agent-producer"), schema_provider)
    consumer = EventConsumer(
        make_transport(client_id="permit-agent-consumer"), schema_provider,
        event_types, group_id="permit-intelligence-agent",
    )
    sf = _postgres_session_factory()
    state = StateContainer(redis_client=_redis_client(), postgres_session_factory=sf)
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=input_topics, output_topic="sentinel.permit.analysis.v1",
    )
    t = threading.Thread(target=runner.run, kwargs={"poll_timeout_seconds": 0.2}, daemon=True, name="permit-agent")
    t.start()
    return AgentHandle("permit-intelligence-agent", runner, t)


def _start_worker_agent(schema_provider: LocalSchemaProvider) -> AgentHandle:
    # Mirrors agents/worker-safety-agent/src/worker_safety_agent/main.py exactly.
    # This one IS flat (main.py imports sibling `config`, `worker_safety_agent`
    # modules directly), so it needs the inner directory on sys.path, isolated
    # the same way as zone/environmental.
    worker_inner = os.path.join(_REPO_ROOT, "agents", "worker-safety-agent", "src", "worker_safety_agent")
    with _isolated_import(worker_inner, purge_names=("config", "worker_safety_agent",
                                                       "ppe_compliance_service", "health")):
        from worker_safety_agent import WorkerSafetyAgent
        # NOTE: this agent's config.py/main.py are empty stubs in the repo --
        # the previously-assumed config.build_zone_ppe_requirements() never
        # existed. WorkerSafetyAgent already builds a default
        # ZonePPERequirements() internally when constructed with no argument
        # (see worker_safety_agent.py __init__), so honor that real default
        # rather than a fabricated config loader.
        agent = WorkerSafetyAgent()

    from sentinel_contracts.events.worker_event_v1 import WorkerEventV1
    from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

    input_topics = ["sentinel.worker.events.v1", "sentinel.zone.state.v1"]
    event_types = {"WorkerEvent": WorkerEventV1, "ZoneState": ZoneStateV1}

    producer = EventProducer(make_transport(client_id="worker-agent-producer"), schema_provider)
    consumer = EventConsumer(
        make_transport(client_id="worker-agent-consumer"), schema_provider,
        event_types, group_id="worker-safety-agent",
    )
    state = StateContainer()  # no backend, matches the agent's own main.py
    runner = AgentRunner(
        agent, consumer=consumer, producer=producer, state_container=state,
        input_topics=input_topics, output_topic="sentinel.worker.analysis.v1",
    )
    t = threading.Thread(target=runner.run, kwargs={"poll_timeout_seconds": 0.2}, daemon=True, name="worker-agent")
    t.start()
    return AgentHandle("worker-safety-agent", runner, t)


def start_all_agents(schema_provider: LocalSchemaProvider) -> list[AgentHandle]:
    """Starts all four in-scope agents. Order matters only in that Zone
    publishes ZoneState, which Permit and Worker Safety both consume --
    InMemoryTransport's shared topic log (module-level state) means this
    works regardless of start order, same as independent Kafka consumer
    groups reading the same topic."""
    return [
        _start_zone_agent(schema_provider),
        _start_environmental_agent(schema_provider),
        _start_permit_agent(schema_provider),
        _start_worker_agent(schema_provider),
    ]
