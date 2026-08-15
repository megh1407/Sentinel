"""
main.py -- SENTINEL API Gateway (Phase 10 backend integration/API layer)

Implements the architecture your master prompt specifies:

    Kafka(-equivalent) -> Backend Integration/API Layer -> Redis/PostgreSQL/Neo4j -> Frontend

Concretely, on startup this process:
  1. Starts the four real, already-verified agents (agents_runtime.py) on
     InMemoryTransport -- the documented, repo-native substitute for a live
     Kafka broker (none is reachable in this environment; swap
     InMemoryTransport for KafkaTransport here to point at a real cluster,
     same as every agent's own main.py already supports).
  2. Starts this layer's own consumer group (state_cache.py) against the
     three analysis topics that have no Redis/Postgres repository yet.
  3. Serves REST reads of real state: ZoneState straight from Redis (the
     agent's own durable store), Environmental/Permit/Worker analysis from
     the in-memory cache above.
  4. Serves a WebSocket that pushes the same real state on every change,
     for the dashboard's live-update requirement.

This file does not compute, simulate, or fabricate any zone/environment/
permit/worker data. Every value it returns was produced by one of the four
real agents processing a real event.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager

import redis as redis_lib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sentinel_eventbus import LocalSchemaProvider
from sentinel_contracts.events.zone_state_v1 import ZoneStateV1

from agents_runtime import start_all_agents
from state_cache import start_state_cache
from orchestrator_runtime import start_orchestrator

_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentinel_eventbus import EventProducer
    from transport_factory import make_transport

    schema_provider = LocalSchemaProvider()
    _state["redis"] = redis_lib.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )
    # Sync Neo4j driver for the API's own topology reads (FastAPI handlers are
    # sync). The orchestrator thread keeps its own async driver; this one only
    # serves /api/topology and seeds the graph idempotently at startup so the
    # dashboard always has real, backend-derived topology to render.
    _state["neo4j"] = None
    try:
        from neo4j import GraphDatabase
        import neo4j_topology

        driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "localdev")),
        )
        driver.verify_connectivity()
        neo4j_topology.seed_default_topology_sync(driver)
        _state["neo4j"] = driver
    except Exception:  # noqa: BLE001 -- topology is optional; API still serves everything else
        import logging
        logging.getLogger(__name__).warning("neo4j_unavailable_for_api_topology", exc_info=True)
    from response_runtime import ResponseAgent
    import transport_factory

    # Real-Kafka mode only: pre-create the topics before any consumer
    # subscribes, so none dies with UNKNOWN_TOPIC_OR_PART. No-op on memory.
    transport_factory.ensure_topics()

    # Postgres: durable audit trail for the dashboard's History page.
    # Optional -- if unreachable, everything else still works, the History
    # page just has nothing to show (same degrade-don't-crash pattern as
    # Neo4j above). Redis/CachingEventPublisher remain the fast live-read
    # path with no retention guarantee; this is what survives a reset.
    _state["history"] = None
    try:
        from sentinel_state.postgres_repositories import build_engine, build_session_factory, HistoryRepository

        pg_dsn = os.environ.get(
            "POSTGRES_DSN", "postgresql://postgres:localdev@localhost:5432/sentinel"
        )
        engine = build_engine(pg_dsn)
        session_factory = build_session_factory(engine)
        history_repo = HistoryRepository(session_factory)
        history_repo.ensure_schema()
        _state["history"] = history_repo
    except Exception:  # noqa: BLE001 -- history is optional; API still serves everything else
        import logging
        logging.getLogger(__name__).warning("postgres_unavailable_for_history", exc_info=True)

    def _persist_assessment(assessment) -> None:
        import logging
        log = logging.getLogger(__name__)

        if _state["history"] is not None:
            try:
                _state["history"].record_risk_assessment(
                    assessment_id=assessment.assessment_id,
                    zone_id=assessment.zone_id,
                    site_id=getattr(assessment, "site_id", None),
                    global_score=float(assessment.global_score.value),
                    severity=assessment.severity.value,
                    decision_category=assessment.decision_category.value,
                    escalation_required=bool(getattr(assessment, "escalation_required", False)),
                    manual_review_required=bool(getattr(assessment, "manual_review_required", False)),
                    explanation=getattr(assessment, "explanation_summary", None) or str(assessment.severity.value),
                )
                log.info("risk_assessment_persisted", extra={"assessment_id": assessment.assessment_id})
            except Exception:  # noqa: BLE001 -- isolated: must never block the Neo4j update below
                log.warning("risk_assessment_persist_failed", exc_info=True,
                            extra={"assessment_id": assessment.assessment_id})

        if _state["neo4j"] is not None:
            try:
                from neo4j_topology import set_zone_status_sync

                set_zone_status_sync(_state["neo4j"], assessment.zone_id, assessment.severity.value)
                log.info("zone_status_updated", extra={"zone_id": assessment.zone_id, "status": assessment.severity.value})
            except Exception:  # noqa: BLE001 -- isolated: topology-status write must never break risk publishing
                log.warning("zone_status_update_failed", exc_info=True, extra={"zone_id": assessment.zone_id})
        else:
            log.info("zone_status_update_skipped_no_neo4j", extra={"zone_id": assessment.zone_id})

    def _persist_action(assessment, decision: dict) -> None:
        if _state["history"] is None:
            return
        payload = decision.get("action_request", {}).get("payload", {})
        _state["history"].record_action_request(
            action_id=payload.get("action_id", decision.get("action_id", "unknown")),
            assessment_id=assessment.assessment_id,
            zone_id=assessment.zone_id,
            action_type=decision.get("action_type", "unknown"),
            urgency=decision.get("urgency", "unknown"),
            classification=decision.get("classification", "unknown"),
            explanation=decision.get("explanation"),
        )

    _state["response"] = ResponseAgent(redis_client=_state["redis"], on_persist=_persist_action)
    _state["agents"] = start_all_agents(schema_provider)
    _state["cache"] = start_state_cache(schema_provider)
    _state["orchestrator"] = start_orchestrator(
        schema_provider, response_agent=_state["response"], on_persist=_persist_assessment
    )
    # Demo-generator producer, wired to the SAME InMemoryTransport process
    # the agents above are consuming from. Kept separate from run_demo.py's
    # own __main__ block, which -- run as a standalone `python run_demo.py`
    # process -- would NOT share this process's in-memory topic log (see
    # that file's module docstring). /api/demo/start below is the honest
    # way to trigger the Phase 11 scenario against a running gateway.
    _state["demo_producer"] = EventProducer(make_transport(client_id="demo-generator"), schema_provider)
    yield
    for handle in _state.get("agents", []):
        handle.stop()


app = FastAPI(title="SENTINEL API Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _redis() -> redis_lib.Redis:
    return _state["redis"]


def _cache():
    return _state["cache"]


def _all_zone_ids() -> list[str]:
    # ZoneStateRepository has no list-all method; scanning its own key
    # namespace (sentinel:zone:state:*) is the minimal read this layer
    # needs to add, not a new state model.
    prefix = "sentinel:zone:state:"
    return [k.decode().removeprefix(prefix) for k in _redis().scan_iter(match=f"{prefix}*")]


def _get_zone_state(zone_id: str) -> ZoneStateV1 | None:
    raw = _redis().get(f"sentinel:zone:state:{zone_id}")
    if raw is None:
        return None
    return ZoneStateV1.model_validate_json(raw)


@app.get("/api/zones")
def list_zones():
    zones = []
    for zone_id in _all_zone_ids():
        zs = _get_zone_state(zone_id)
        if zs is None:
            continue
        env = _cache().environment_for_zone(zs.site_id, zone_id)
        permits = _cache().permits_for_zone(zone_id)
        workers = _cache().workers_for_zone(zone_id)
        zones.append({
            "zone_state": zs.model_dump(mode="json"),
            "environment": env.model_dump(mode="json") if env else None,
            "active_permits": [p.model_dump(mode="json") for p in permits],
            "workers": [w.model_dump(mode="json") for w in workers],
        })
    return {"zones": zones}


@app.get("/api/zones/{zone_id}")
def get_zone(zone_id: str):
    zs = _get_zone_state(zone_id)
    if zs is None:
        raise HTTPException(status_code=404, detail=f"no ZoneState cached for zone_id={zone_id!r}")
    env = _cache().environment_for_zone(zs.site_id, zone_id)
    permits = _cache().permits_for_zone(zone_id)
    workers = _cache().workers_for_zone(zone_id)
    return {
        "zone_state": zs.model_dump(mode="json"),
        "environment": env.model_dump(mode="json") if env else None,
        "active_permits": [p.model_dump(mode="json") for p in permits],
        "workers": [w.model_dump(mode="json") for w in workers],
    }


@app.get("/api/environment")
def list_environment():
    return {"readings": [e.model_dump(mode="json") for e in _cache().all_environment()]}


@app.get("/api/permits")
def list_permits():
    return {"permits": [p.model_dump(mode="json") for p in _cache().all_permits()]}


@app.get("/api/permits/{permit_id}")
def get_permit(permit_id: str):
    p = _cache().permit(permit_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"no PermitAnalysis cached for permit_id={permit_id!r}")
    return p.model_dump(mode="json")


@app.get("/api/workers")
def list_workers():
    return {"workers": [w.model_dump(mode="json") for w in _cache().all_workers()]}


@app.get("/api/workers/{worker_id}")
def get_worker(worker_id: str):
    w = _cache().worker(worker_id)
    if w is None:
        raise HTTPException(status_code=404, detail=f"no WorkerAnalysis cached for worker_id={worker_id!r}")
    return w.model_dump(mode="json")


@app.post("/api/demo/start")
def start_demo():
    """Runs the Phase 11 T0-T5 scenario (scripts/demo/run_demo.py) against
    THIS process's agents. Runs in a background thread so the HTTP request
    returns immediately; poll /api/zones or the WebSocket to watch it land."""
    import sys
    import threading as _threading
    demo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "demo")
    if demo_dir not in sys.path:
        sys.path.insert(0, demo_dir)
    import run_demo as demo_mod

    def _run():
        demo_mod.run_demo(_state["demo_producer"], tick_seconds=2.0)

    _threading.Thread(target=_run, daemon=True, name="demo-scenario").start()
    return {"status": "started", "scenario": "T0-T5 zone-A convergence"}


@app.post("/api/demo/scenario/{name}")
def run_scenario(name: str):
    """Injects one named scenario's real events into the live pipeline
    (Phase 9). Runs in a background thread; watch /api/risk-assessments,
    /api/action-requests, or the WebSocket for the result."""
    import threading as _threading
    import demo_scenarios

    fn = demo_scenarios.SCENARIOS.get(name)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown scenario {name!r}; choose one of {sorted(demo_scenarios.SCENARIOS)}",
        )

    _threading.Thread(target=lambda: fn(_state["demo_producer"]),
                      daemon=True, name=f"scenario-{name}").start()
    return {"status": "started", "scenario": name}


@app.post("/api/demo/reset")
def reset_demo():
    """Resets DEMO state only: live zone state in Redis, cached assessments,
    cached analyses, and Response Agent idempotency. Does NOT delete unrelated
    historical/audit data."""
    # Demo LIVE operational state only (Redis). NOT Postgres audit/history --
    # those are the historical layer the prompt says must survive a reset.
    _DEMO_STATE_PREFIXES = (
        "sentinel:zone:",            # zone agent live state
        "sentinel:v1:zone",          # risk orchestrator rolling per-zone context
        "sentinel:worker:",          # worker presence
        "sentinel:response:idempotency:",  # response idempotency
        "permit_agent:seen_event:",  # permit agent dedupe (so re-run reprocesses)
        "zone_intelligence:known_zone_ids",
    )
    cleared_zones = 0
    r = _redis()
    for prefix in _DEMO_STATE_PREFIXES:
        for key in list(r.scan_iter(match=f"{prefix}*")):
            if key.decode().startswith("sentinel:zone:state"):
                cleared_zones += 1
            r.delete(key)
    _cache().reset()
    orch = _state.get("orchestrator")
    if orch is not None:
        orch.publisher.clear()
    resp = _state.get("response")
    if resp is not None:
        resp.reset()
    # Environmental Agent keeps its own in-process sensor-buffer and history
    # state (SensorSnapshotAggregator, HistoryManager) -- neither is Redis-
    # backed, so nothing above touches it. Without this, a previous
    # scenario's readings silently bleed into the next run's assessment.
    for handle in _state.get("agents", []):
        if handle.name == "environmental-intelligence-agent" and handle.agent is not None:
            if hasattr(handle.agent, "reset_demo_state"):
                handle.agent.reset_demo_state()
    # Reset topology node statuses back to normal.
    driver = _state.get("neo4j")
    if driver is not None:
        try:
            import neo4j_topology
            neo4j_topology.seed_default_topology_sync(driver)  # MERGE re-normalizes statuses
        except Exception:  # noqa: BLE001
            pass
    return {"status": "reset", "zones_cleared": cleared_zones}


def _serialize_assessment(a) -> dict:
    """SystemRiskAssessment has no built-in .to_dict() -- this mirrors
    exactly the fields the master prompt's output contract lists, pulled
    from the real dataclass fields (see agents/risk-orchestrator-agent/
    src/risk_orchestrator_agent/domain/models/system_risk_assessment.py)."""
    return {
        "assessment_id": a.assessment_id,
        "event_id": a.event_id,
        "correlation_id": a.correlation_id,
        "site_id": a.site_id,
        "zone_id": a.zone_id,
        "computed_at": a.computed_at.isoformat(),
        "global_score": a.global_score.value,
        "local_risk": a.global_score.local.score,
        "interaction_risk": a.global_score.interaction.score,
        "severity": a.severity.value,
        "decision_category": a.decision_category.value,
        "confidence": a.confidence,
        "contributing_factors": list(a.contributing_factors),
        "propagation_paths": [
            {"from_zone": p.from_zone_id, "to_zone": p.to_zone_id, "relationship_type": p.relationship_type}
            for p in a.propagation_paths
        ],
        "explanation": a.explanation,
        "escalation_required": a.escalation_required,
        "manual_review_required": a.manual_review_required,
        "analysis_completeness": a.analysis_completeness,
        "missing_domains": list(a.missing_domains),
        "risk_level_changed": a.risk_level_changed,
        "previous_severity": a.previous_severity,
    }


@app.get("/api/risk-assessments")
def list_risk_assessments():
    """Real SystemRiskAssessment output from the merged Risk Orchestrator
    (agents/risk-orchestrator-agent), one per zone that has been assessed
    since this process started. See that package's docs/RECONCILIATION_REPORT.md
    and this gateway's orchestrator_bridge.py for exactly which inputs are
    real vs. bridged."""
    return {"assessments": [_serialize_assessment(a) for a in _state["orchestrator"].publisher.all_latest()]}


@app.get("/api/risk-assessments/{zone_id}")
def get_risk_assessment(zone_id: str):
    a = _state["orchestrator"].publisher.latest_for_zone(zone_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"no risk assessment yet for zone_id={zone_id!r}")
    return _serialize_assessment(a)


@app.get("/api/action-requests")
def list_action_requests():
    """Real ActionRequests produced by the Response Agent, one per zone that
    has been assessed. Each is derived from the finalized SystemRiskAssessment
    -- the Response Agent never recalculates risk."""
    return {"responses": _state["response"].all_latest()}


@app.get("/api/history")
def list_history(limit: int = 50):
    """Real, durably persisted risk-assessment + action-request history from
    Postgres -- survives demo resets and process restarts, unlike Redis's
    live-state cache. Empty (not an error) if Postgres was unreachable at
    startup; the dashboard should show that as 'no history yet', not fake data."""
    if _state["history"] is None:
        return {"history": [], "available": False}
    return {"history": _state["history"].get_history(limit=limit), "available": True}


def _explanation_for_zone(zone_id: str):
    """Shared helper: builds a SafetyExplanation from the same live
    assessment + action objects the rest of the API already serves.
    Raises HTTPException(404) if no assessment exists yet for this zone --
    callers should let that propagate, not fabricate a placeholder."""
    from safety_explanation import build_explanation

    a = _state["orchestrator"].publisher.latest_for_zone(zone_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"no risk assessment yet for zone_id={zone_id!r}")
    assessment = _serialize_assessment(a)
    action = _state["response"].latest_for_zone(zone_id)
    return build_explanation(assessment, action)


@app.get("/api/explanation/{zone_id}")
def get_explanation(zone_id: str):
    """Deterministic Safety Explanation -- always available, no LLM
    required. This is the fallback the dashboard shows immediately, with
    the LLM-enhanced version (if configured) layered on top asynchronously
    via /api/copilot/ask -- never the other way around (Phase 13/14)."""
    return _explanation_for_zone(zone_id).to_dict()


@app.post("/api/copilot/ask")
async def copilot_ask(payload: dict):
    """LLM Safety Copilot, constrained to verified assessment data only.
    zone_id and question are required. Always returns a usable answer --
    'source' in the response tells the frontend whether it came from the
    LLM or the deterministic fallback, so it can be labeled honestly."""
    import safety_copilot

    zone_id = payload.get("zone_id")
    question = payload.get("question", "").strip()
    if not zone_id or not question:
        raise HTTPException(status_code=400, detail="zone_id and question are required")

    explanation = _explanation_for_zone(zone_id)
    return safety_copilot.ask(explanation, question)


@app.get("/api/copilot/brief/{zone_id}")
async def copilot_brief(zone_id: str):
    """LLM-enhanced conversational summary (falls back to deterministic)."""
    import safety_copilot

    explanation = _explanation_for_zone(zone_id)
    return safety_copilot.explain_conversationally(explanation)


@app.get("/api/action-requests/{zone_id}")
def get_action_request(zone_id: str):
    r = _state["response"].latest_for_zone(zone_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"no response yet for zone_id={zone_id!r}")
    return r


@app.get("/api/topology")
def get_topology():
    """Zone relationship graph, read straight from Neo4j (the same graph the
    Risk Orchestrator queries for propagation). The dashboard renders this --
    it does not invent topology. 503 if Neo4j is not wired."""
    driver = _state.get("neo4j")
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j topology not available")
    import neo4j_topology
    return neo4j_topology.read_topology_sync(driver)


@app.get("/api/health")
def health():
    import transport_factory

    redis_ok = False
    try:
        redis_ok = bool(_redis().ping())
    except Exception:  # noqa: BLE001
        redis_ok = False

    postgres_ok = _state.get("history") is not None

    neo4j_ok = False
    if _state.get("neo4j") is not None:
        try:
            _state["neo4j"].verify_connectivity()
            neo4j_ok = True
        except Exception:  # noqa: BLE001
            neo4j_ok = False

    transport_mode = transport_factory.transport_kind()
    kafka_ok = None  # unknown/not applicable in memory mode
    if transport_mode == "kafka":
        try:
            from confluent_kafka.admin import AdminClient

            admin = AdminClient({"bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")})
            admin.list_topics(timeout=3.0)
            kafka_ok = True
        except Exception:  # noqa: BLE001
            kafka_ok = False

    agents = [h.name for h in _state.get("agents", [])]

    return {
        "status": "ok",
        "transport_mode": transport_mode,
        "components": {
            "redis": redis_ok,
            "postgres": postgres_ok,
            "neo4j": neo4j_ok,
            "kafka": kafka_ok,  # null when transport_mode != "kafka" -- N/A, not "down"
        },
        "agents": agents,
        "agents_active": len(agents),
        "orchestrator_active": _state.get("orchestrator") is not None,
        "response_agent_active": _state.get("response") is not None,
        "zones_known": len(_all_zone_ids()),
    }


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """Polls the same real state this REST API serves and pushes it on
    every change. Simple diff-by-JSON-string, not a message bus of its
    own -- Redis/the in-memory cache remain the single source of truth."""
    await websocket.accept()
    last_payload = None
    try:
        while True:
            payload = json.dumps(list_zones(), sort_keys=True, default=str)
            if payload != last_payload:
                await websocket.send_text(payload)
                last_payload = payload
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
