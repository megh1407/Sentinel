# SENTINEL — Demo Status (as of this handoff)

This is the state of the repo after a live test-and-fix session. Everything
below was actually run, not assumed. Commands to reproduce are at the bottom.

## What's confirmed WORKING (verified live, this session)

- **Zone Agent → Environmental/Permit/Worker-Safety Agents → Risk Orchestrator
  → Response Agent**, end to end, using `InMemoryTransport` in place of a
  live Kafka broker (a documented substitution already used elsewhere in
  this codebase — swap to real Kafka is a config change, not a rewrite).
- **Redis**: real, used for zone state, permit dedup, response idempotency.
- **Response Agent** (`agents/response-agent`): was broken on arrival —
  its own README claimed contract fields existed that didn't. Fixed by
  hand-syncing `sentinel_contracts/events/risk_score_v1.py` and
  `action_request_v1.py` to the `.avsc` source of truth, and fixing the
  `agents.yaml` registry entry. **28/28 unit tests pass.**
- **`platform-services/api-gateway`**: a FastAPI app that wires
  Zone/Environmental/Permit/Worker-Safety agents, the Risk Orchestrator,
  and the Response Agent into one live process, with `/api/demo/*`
  endpoints to drive scenarios. This already existed — I ran it, didn't
  build it.
- **Demo scenarios, run live against the gateway**:
  - `gas-rise` (single-agent hazard) → CRITICAL, score 59.5–76.7 depending
    on run
  - `compound-risk` (multi-agent) → **CATASTROPHIC, score 93.44, decision =
    EMERGENCY, action = EVACUATE_ZONE, urgency IMMEDIATE**, real
    contributing factors (gas + PPE violation + hot-work permit + temp)
  - `normal` → correctly negligible/safe, score 0.0
  - `multi-zone-emergency` → each zone scores correctly and independently,
    **but propagation_paths is empty** — see "NOT working" below
- **`/api/demo/reset`**: fixed this session. It only cleared Redis before;
  the Environmental Agent's own in-process `SensorSnapshotAggregator` and
  `HistoryManager` never got cleared, so old readings/trends bled into the
  next scenario (e.g. "normal" showed CATASTROPHIC because of leftover
  state from a prior run). Verified fixed: reset → compound-risk → reset →
  normal → reset → gas-rise → reset → compound-risk again, all correct and
  repeatable.
- **Dashboard wiring**: `dashboard/lib/api.ts` already points at
  `localhost:8000` with real fetch calls, falling back to
  `dashboard/lib/mockData.ts` only if the fetch fails. Not visually
  confirmed in a browser — see "NOT verified" below.

## What's NOT working

- **Neo4j / topology / propagation risk.** No Neo4j server was reachable
  in the sandbox this was built in (not installable via plain `apt`, needs
  Neo4j's own package repo). The gateway degrades gracefully instead of
  crashing, but multi-zone propagation is genuinely dead until Neo4j is up.
- **Kafka.** Never live-tested against a real broker in this session — only
  `InMemoryTransport`. Should work with a config change, but "should" is
  not "verified."
- **PostgreSQL.** Not exercised by anything in this pipeline run.

## What's NOT verified (not broken, just unchecked)

- The actual dashboard UI rendering in a browser — this sandbox has no
  browser and the gateway isn't reachable from outside it.
- `config.py` / `health.py` / `memory/` inside `agents/response-agent` —
  empty stubs, presumably meant to defer to the shared `sentinel_state`/
  `sentinel_agent_sdk` libs, but not confirmed intentional.

## How to run it for real

```bash
# 1. Start real infra (Redis, Postgres, Kafka, schema-registry, Neo4j)
docker compose -f scripts/dev-env/docker-compose.yml up -d

# 2. Install Python deps
pip install -r requirements.txt --break-system-packages
pip install fastapi "uvicorn[standard]" confluent-kafka neo4j psycopg2-binary --break-system-packages

# 3. Launch the gateway
cd platform-services/api-gateway
PYTHONPATH=$(pwd)/../../libs:$(pwd)/../..:$(pwd)/../../sentinel_contracts:. \
  python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 4. In another terminal, launch the dashboard
cd dashboard
npm install
npm run dev

# 5. Drive a scenario
curl -X POST http://localhost:8000/api/demo/scenario/compound-risk
curl http://localhost:8000/api/risk-assessments
curl http://localhost:8000/api/action-requests

# Reset between runs
curl -X POST http://localhost:8000/api/demo/reset
```

Available scenarios: `normal`, `gas-rise`, `compound-risk`,
`multi-zone-emergency` (this last one needs Neo4j actually running to show
propagation — without it, zones still score correctly, just independently).

## Files changed this session (if diffing against your GitHub repo)

- `agents/response-agent/` — merged in, was not previously in the repo
- `sentinel_contracts/events/risk_score_v1.py` — hand-synced additive fields
- `sentinel_contracts/events/action_request_v1.py` — hand-synced additive
  fields + new enums (`ActionPriority`, `ActionLifecycleState`)
- `contracts/agent-registry/agents.yaml` — fixed response_agent's
  consumes/dependencies entry
- `agents/environmental-intelligence-agent/sensor_snapshot_aggregator.py` —
  added `clear_all()`
- `agents/environmental-intelligence-agent/engine/history_manager.py` —
  added `HistoryManager.clear()`
- `agents/environmental-intelligence-agent/environmental_intelligence_agent.py`
  — added `reset_demo_state()`
- `platform-services/api-gateway/agents_runtime.py` — `AgentHandle` now
  carries the live agent instance
- `platform-services/api-gateway/main.py` — `/api/demo/reset` now also
  resets the Environmental Agent's in-process state
