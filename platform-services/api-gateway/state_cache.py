"""
state_cache.py

The API-gateway's own read-side cache for EnvironmentAnalysis, PermitAnalysis,
and WorkerAnalysis -- the three output types that (per the Phase 1/2 agent
audit) have NO Redis or PostgreSQL repository anywhere in the repo today.
ZoneState is deliberately NOT duplicated here: it already has a real,
verified Redis repository (ZoneStateRepository), so the API layer reads it
directly from Redis in main.py, matching the Phase 10 architecture

    Kafka -> Backend Integration/API Layer -> Redis/PostgreSQL/Neo4j -> Frontend

This module is this API layer's own Kafka(-equivalent) consumer group --
it subscribes independently to the three analysis topics, exactly like a
fourth, independent consumer would against a real broker. It does not
replace or wrap the agents' own consumers.
"""
from __future__ import annotations

import threading

from sentinel_eventbus import EventConsumer, LocalSchemaProvider

from transport_factory import make_transport
from sentinel_contracts.agent_contracts.environment_analysis_v1 import EnvironmentAnalysisV1
from sentinel_contracts.agent_contracts.permit_analysis_v1 import PermitAnalysisV1
from sentinel_contracts.agent_contracts.worker_analysis_v1 import WorkerAnalysisV1


class StateCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # keyed by (site_id, zone_id) -> latest event, newest wins
        self._environment: dict[tuple[str, str], EnvironmentAnalysisV1] = {}
        self._permits: dict[str, PermitAnalysisV1] = {}
        self._workers: dict[str, WorkerAnalysisV1] = {}

    # -- handlers, invoked by EventConsumer on its poll loop thread --------

    def _on_environment(self, event: EnvironmentAnalysisV1) -> None:
        with self._lock:
            self._environment[(event.site_id, event.zone_id)] = event

    def _on_permit(self, event: PermitAnalysisV1) -> None:
        with self._lock:
            self._permits[event.payload.permit_id] = event

    def _on_worker(self, event: WorkerAnalysisV1) -> None:
        with self._lock:
            self._workers[event.payload.worker_id] = event

    # -- reads, called from FastAPI request handlers ------------------------

    def environment_for_zone(self, site_id: str, zone_id: str) -> EnvironmentAnalysisV1 | None:
        with self._lock:
            return self._environment.get((site_id, zone_id))

    def all_environment(self) -> list[EnvironmentAnalysisV1]:
        with self._lock:
            return list(self._environment.values())

    def permit(self, permit_id: str) -> PermitAnalysisV1 | None:
        with self._lock:
            return self._permits.get(permit_id)

    def permits_for_zone(self, zone_id: str) -> list[PermitAnalysisV1]:
        with self._lock:
            return [p for p in self._permits.values() if p.zone_id == zone_id]

    def all_permits(self) -> list[PermitAnalysisV1]:
        with self._lock:
            return list(self._permits.values())

    def worker(self, worker_id: str) -> WorkerAnalysisV1 | None:
        with self._lock:
            return self._workers.get(worker_id)

    def workers_for_zone(self, zone_id: str) -> list[WorkerAnalysisV1]:
        with self._lock:
            return [w for w in self._workers.values() if w.zone_id == zone_id]

    def all_workers(self) -> list[WorkerAnalysisV1]:
        with self._lock:
            return list(self._workers.values())

    def reset(self) -> None:
        """Clears cached analysis state (demo reset only)."""
        with self._lock:
            self._environment.clear()
            self._permits.clear()
            self._workers.clear()


def start_state_cache(schema_provider: LocalSchemaProvider) -> StateCache:
    cache = StateCache()
    event_types = {
        "EnvironmentAnalysis": EnvironmentAnalysisV1,
        "PermitAnalysis": PermitAnalysisV1,
        "WorkerAnalysis": WorkerAnalysisV1,
    }
    consumer = EventConsumer(
        make_transport(client_id="api-gateway-state-cache"), schema_provider,
        event_types, group_id="api-gateway",
    )

    def _dispatch(event):
        if isinstance(event, EnvironmentAnalysisV1):
            cache._on_environment(event)
        elif isinstance(event, PermitAnalysisV1):
            cache._on_permit(event)
        elif isinstance(event, WorkerAnalysisV1):
            cache._on_worker(event)

    consumer.subscribe(
        [
            "sentinel.environment.analysis.v1",
            "sentinel.permit.analysis.v1",
            "sentinel.worker.analysis.v1",
        ],
        handler=_dispatch,
    )

    def _poll_loop():
        while True:
            consumer.poll_once(0.2)

    t = threading.Thread(target=_poll_loop, daemon=True, name="api-gateway-state-cache")
    t.start()
    return cache
