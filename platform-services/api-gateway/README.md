# SENTINEL API Gateway

The Phase 10 "Backend Integration/API Layer" from the master integration
prompt:

    Kafka(-equivalent) -> Backend Integration/API Layer -> Redis/PostgreSQL/Neo4j -> Frontend API/WebSocket -> Dashboard

## What this is, concretely

- `agents_runtime.py` starts the four real, independently-verified agents
  (Zone, Environmental, Permit, Worker Safety -- Risk Orchestrator and
  Response Agent are out of scope and untouched) as `AgentRunner`
  instances, each on its own thread, wired through `InMemoryTransport`
  instead of `KafkaTransport`. Every topic name / event-type mapping is
  copied verbatim from that agent's own real `main.py`.
- `state_cache.py` is this layer's own consumer group against the three
  analysis topics that have no Redis/Postgres repository yet
  (Environment/Permit/Worker analysis). ZoneState is NOT duplicated here
  -- it's read straight from the real `ZoneStateRepository` in Redis.
- `main.py` is the FastAPI app: REST reads of all of the above, a
  WebSocket that pushes zone state on change, and `POST /api/demo/start`
  to run the Phase 11 scenario against this process's agents.

## Why InMemoryTransport and not KafkaTransport

No live Kafka broker was reachable in the environment this was built and
verified in (no Docker, egress restricted to package registries). The
real compose stack for Kafka/Redis/Postgres/Neo4j already exists at
`scripts/dev-env/docker-compose.yml` -- when you have Docker available:

1. In `agents_runtime.py`, replace each `InMemoryTransport(...)` with
   `KafkaTransport(bootstrap_servers=..., client_id=...)` -- same
   constructor shape every agent's own `main.py` already uses.
2. In `main.py`'s `/api/demo/start` and `scripts/demo/run_demo.py`, do the
   same for the demo producer.
3. `docker compose -f scripts/dev-env/docker-compose.yml up -d`, then run
   this gateway and the demo script as normal, separate OS processes --
   they'll share state through the real broker instead of needing to be
   in the same Python interpreter.

**Important nuance discovered while building this**: with `InMemoryTransport`,
the topic log is process-wide, in-memory state (see
`libs/sentinel_eventbus/in_memory_transport.py`) -- it is NOT shared across
separate `python` processes. That's why `/api/demo/start` runs the demo
scenario in a background thread of the *same* process as the agents,
rather than shelling out to `scripts/demo/run_demo.py` as a subprocess.
Running `python scripts/demo/run_demo.py` on its own, separately from a
running gateway process, will NOT be visible to that gateway -- only to
its own local (and otherwise empty) InMemoryTransport instance.

## Running it (verified working in this environment)

```bash
# from repo root
pip install -r requirements.txt
pip install -r platform-services/api-gateway/requirements.txt

redis-server --daemonize yes
# optional: export POSTGRES_DSN=postgresql://... for durable Zone Agent persistence

cd platform-services/api-gateway
REDIS_HOST=localhost uvicorn main:app --host 0.0.0.0 --port 8000
```

Then, in another terminal:

```bash
curl -X POST http://localhost:8000/api/demo/start
curl http://localhost:8000/api/zones
curl http://localhost:8000/api/permits
curl http://localhost:8000/api/workers
```

This was run end-to-end in this environment (via FastAPI's `TestClient`,
since background OS processes aren't preserved across tool calls in the
sandbox this was built in) and produced real output from all four agents,
including the Permit Agent's honest `BLOCKED_BY_INPUT_CONTRACT` reporting
and the Worker Safety Agent's real PPE-violation detection -- not
fabricated fixtures. See the accompanying integration report for the full
transcript.

## Known real gaps, not hidden

- **Neo4j is not wired here at all.** No graph queries are exposed by this
  API layer yet -- `graph_projection_service.py` (Zone Agent) is the only
  Neo4j-writing code in the repo, and it's unverified live (no Neo4j
  reachable in this environment; see the integration report).
- **B3 (gas-species disambiguation)** is still unresolved at the contract
  layer (`SensorType.GAS` is undifferentiated) -- `/api/environment`
  responses will never show named gas species until that contract change
  lands. Not something this API layer can paper over.
- **No auth, no rate limiting, no production error handling** -- this is a
  demo-grade integration layer proving the real data path works, not a
  hardened service.
