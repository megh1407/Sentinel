"""
orchestrator_runtime.py

Wires the merged Risk Orchestrator (agents/risk-orchestrator-agent) into
this API gateway process as a real consumer of the 4 real, already-
verified SENTINEL topics (ZoneState, EnvironmentAnalysis, PermitAnalysis,
WorkerAnalysis), using the SAME InMemoryTransport-based approach as
agents_runtime.py -- for the same reason (no live Kafka broker reachable
in this environment; documented as a one-line KafkaTransport swap).

The Orchestrator's own code (agents/risk-orchestrator-agent/src/...) is
untouched -- this module only translates real events into the raw dicts
its real, unmodified AgentResultDTO.from_raw()/EventRouter.route() already
expect (see orchestrator_bridge.py), then calls that real, unmodified
code path.

ONE new architectural piece not present in either the orchestrator
package or agents_runtime.py: the Orchestrator's ContextRepositoryPort
needs an ASYNC Redis client (redis.asyncio.Redis), while every other
agent in this integration pass uses the sync `redis` client. Constructing
an async client and running the Orchestrator's consume loop both happen
inside ONE dedicated asyncio event loop, in this module's own thread --
async Redis clients are loop-bound, so this loop must be created once and
reused for the Orchestrator's entire lifetime, not per-call.
"""
from __future__ import annotations

import asyncio
import os
import threading

from sentinel_eventbus import EventConsumer, InMemoryTransport, LocalSchemaProvider

import orchestrator_bridge as bridge

_INBOUND_TOPICS = (
    "sentinel.zone.state.v1",
    "sentinel.environment.analysis.v1",
    "sentinel.permit.analysis.v1",
    "sentinel.worker.analysis.v1",
)

_TRANSLATORS = {
    "ZoneState": bridge.zone_state_to_zone_analysis_raw,
    "EnvironmentAnalysis": bridge.environment_analysis_to_raw,
    "PermitAnalysis": bridge.permit_analysis_to_raw,
    "WorkerAnalysis": bridge.worker_analysis_to_raw,
}

# The topic string EventRouter.route() validates against for each real
# inbound topic. ZoneState arrives on sentinel.zone.state.v1 but is
# re-badged as sentinel.zone.analysis.v1 here -- see orchestrator_bridge.py's
# module docstring for why.
_ROUTE_TOPIC = {
    "ZoneState": "sentinel.zone.analysis.v1",
    "EnvironmentAnalysis": "sentinel.environment.analysis.v1",
    "PermitAnalysis": "sentinel.permit.analysis.v1",
    "WorkerAnalysis": "sentinel.worker.analysis.v1",
}


class OrchestratorHandle:
    def __init__(self, publisher: "bridge.CachingEventPublisher", thread: threading.Thread):
        self.publisher = publisher
        self._thread = thread


def start_orchestrator(schema_provider: LocalSchemaProvider) -> OrchestratorHandle:
    publisher = bridge.CachingEventPublisher()
    ready = threading.Event()

    def _thread_main() -> None:
        asyncio.run(_orchestrator_main(schema_provider, publisher, ready))

    t = threading.Thread(target=_thread_main, daemon=True, name="risk-orchestrator")
    t.start()
    ready.wait(timeout=5.0)
    return OrchestratorHandle(publisher, t)


async def _orchestrator_main(schema_provider: LocalSchemaProvider, publisher, ready: threading.Event) -> None:
    import sys
    import redis.asyncio as aioredis

    orchestrator_src = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "agents", "risk-orchestrator-agent", "src",
    ))
    if orchestrator_src not in sys.path:
        sys.path.insert(0, orchestrator_src)

    from risk_orchestrator_agent.main import build_orchestrator
    from risk_orchestrator_agent.memory.repository_manager import RepositoryManager

    redis_client = aioredis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )
    # postgres_pool/neo4j_driver intentionally None -- HistoryRepositoryPort/
    # GraphRepositoryPort are optional (ContextBuilder treats them as
    # "that domain is absent", never as a crash), and neither Postgres nor
    # Neo4j async clients were available to wire honestly in this pass.
    repository_manager = RepositoryManager.from_clients(redis_client=redis_client)
    orchestrator, event_router = build_orchestrator(repository_manager, publisher=publisher)

    from sentinel_contracts.events.zone_state_v1 import ZoneStateV1
    from sentinel_contracts.agent_contracts.environment_analysis_v1 import EnvironmentAnalysisV1
    from sentinel_contracts.agent_contracts.permit_analysis_v1 import PermitAnalysisV1
    from sentinel_contracts.agent_contracts.worker_analysis_v1 import WorkerAnalysisV1

    event_types = {
        "ZoneState": ZoneStateV1,
        "EnvironmentAnalysis": EnvironmentAnalysisV1,
        "PermitAnalysis": PermitAnalysisV1,
        "WorkerAnalysis": WorkerAnalysisV1,
    }

    consumer = EventConsumer(
        InMemoryTransport(client_id="risk-orchestrator-consumer"), schema_provider,
        event_types, group_id="risk-orchestrator",
    )

    pending: list[tuple[str, dict]] = []

    def _on_event(event) -> None:
        kind = event.event_type  # e.g. "ZoneState" -- NOT type(event).__name__, which is "ZoneStateV1"
        translator = _TRANSLATORS.get(kind)
        if translator is None:
            return
        raw_event = event.model_dump(mode="json")
        raw_envelope = translator(raw_event)
        pending.append((_ROUTE_TOPIC[kind], raw_envelope))

    consumer.subscribe(list(_INBOUND_TOPICS), handler=_on_event)

    ready.set()
    while True:
        consumer.poll_once(0.2)
        while pending:
            topic, raw = pending.pop(0)
            try:
                await event_router.route(topic, raw)
            except Exception:  # noqa: BLE001 -- never let one bad event kill the orchestrator loop
                import logging
                logging.getLogger(__name__).exception("orchestrator_route_failed", extra={"topic": topic})
        await asyncio.sleep(0.05)
