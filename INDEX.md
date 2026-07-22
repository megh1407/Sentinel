# SENTINEL — Complete Integration Package (this session)

Everything built, verified, and fixed across this whole integration effort,
in one archive. Unzip into your repo root, preserving paths — every file
here either replaces an empty/stale file or is new; nothing overwrites
working agent business logic.

## What's in here, in the order it was built

### 1. Backend integration layer (Phase 10/11 of the original SENTINEL master prompt)
```
platform-services/api-gateway/agents_runtime.py    -- starts the 4 real agents (Zone/Environmental/Permit/Worker)
platform-services/api-gateway/state_cache.py        -- read-side cache for Environment/Permit/Worker analysis
platform-services/api-gateway/main.py                -- FastAPI: REST + WebSocket + demo trigger + risk assessments
platform-services/api-gateway/requirements.txt
platform-services/api-gateway/README.md
scripts/demo/run_demo.py                             -- T0-T5 scenario generator
scripts/demo/README.md
```
See `MANIFEST_INTEGRATION_DELIVERABLES.md` for the full verification trail
(what was live-tested, what's still mock-fallback, real bugs found and
fixed along the way).

### 2. Dashboard wiring — real data instead of mock fixtures
```
dashboard/lib/api.ts                          -- real fetch client
dashboard/lib/contracts.ts                     -- fixed a stale "simulated" doc comment
dashboard/app/page.tsx                          -- async, live-vs-mock fallback
dashboard/app/zones/[zoneId]/page.tsx           -- same, for the zone detail page
dashboard/components/ContributingSignals.tsx    -- honest live/simulated SourceTag
```

### 3. Gas detection (B3 resolution) + visual gauges
```
agents/environmental-intelligence-agent/sensor_snapshot_aggregator.py   -- per-species gas readings, not dropped
agents/environmental-intelligence-agent/environmental_intelligence_agent.py  -- per-gas hazard classification + real threshold_ppm
dashboard/components/GasLevelMeter.tsx           -- the vertical banded gauge (per your reference image)
dashboard/components/GasTable.tsx                -- renders one gauge per gas, above the existing table
```
Real, verified example: methane 900ppm/5000ppm-critical = 18%, CO
40ppm/175ppm-critical = 23%, H2S 3ppm/50ppm-critical = 6% (all against
real, already-configured `ThresholdService` thresholds — nothing invented).

### 4. Risk Orchestrator merge — the system-level risk intelligence layer
```
agents/risk-orchestrator-agent/**                    -- full merged package (108 files), replaces the empty scaffold
platform-services/api-gateway/orchestrator_bridge.py   -- explicit adapter: real events -> Orchestrator's expected shape
platform-services/api-gateway/orchestrator_runtime.py  -- starts the Orchestrator as a real 5th consumer
```
See `RISK_ORCHESTRATOR_MERGE_REPORT.md` for the full 13-part deliverable
(responsibility matrix, canonical contracts, data/orchestrator/response/
storage flow, test results, known limitations, extension points).

**Real, verified end-to-end result** (this is the whole system working
together, all four pieces above, in one run): the demo scenario's PPE
violation + temperature breach + methane breach + CO breach combine into
a real `SystemRiskAssessment`:
```
severity: CATASTROPHIC | global_score: 86.54 | decision: EMERGENCY
contributing_factors:
  - Worker W-001 has PPE violations: ['vest']
  - high_temperature at 61.0C exceeds threshold (stable) in zone ZONE-A
  - flammable_gas at 900.0ppm exceeds threshold (stable) in zone ZONE-A
  - toxic_gas at 40.0ppm exceeds threshold (stable) in zone ZONE-A
```
Available live at `GET /api/risk-assessments` once the gateway is running.

## Setup, in order

```bash
# 1. infra
redis-server --daemonize yes
pip install -r requirements.txt
pip install -r platform-services/api-gateway/requirements.txt
pip install -r agents/risk-orchestrator-agent/pyproject.toml   # or: pip install -e agents/risk-orchestrator-agent

# 2. backend
cd platform-services/api-gateway
REDIS_HOST=localhost uvicorn main:app --host 0.0.0.0 --port 8000

# 3. trigger the demo (separate terminal)
curl -X POST http://localhost:8000/api/demo/start
curl http://localhost:8000/api/zones
curl http://localhost:8000/api/risk-assessments

# 4. dashboard (separate terminal)
cd dashboard
npm install
NEXT_PUBLIC_SENTINEL_API_BASE=http://localhost:8000 npm run build
NEXT_PUBLIC_SENTINEL_API_BASE=http://localhost:8000 npm start
```

## Honest, cross-cutting limitations (not repeated per-file — see the two reports above for detail)

- No live Kafka or Neo4j anywhere in this package — `InMemoryTransport`
  throughout, documented as a one-line `KafkaTransport` swap per call site.
- `maintenance-intelligence-agent` and `incident-intelligence-agent` are
  confirmed 0-line scaffolds — the Orchestrator correctly reports them as
  `missing_domains`, not silently ignored.
- Response Agent does not exist — the Orchestrator's real output has a
  real REST consumer, but nothing acts on it downstream yet.
- No automated test coverage was added for this session's own integration
  code (the bridge/runtime/dashboard-wiring layers) — everything here was
  verified by direct, manual end-to-end runs recorded in the two reports,
  not by a CI-style test suite.
